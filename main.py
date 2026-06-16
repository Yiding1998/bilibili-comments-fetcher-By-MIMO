#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站弹幕与评论统计工具 v2.0

功能：
- 获取视频弹幕（使用protobuf解析）
- 获取评论（使用Wbi签名）
- 断点续传
- 自适应限流
- 导出Excel报表

用法：
    python main.py BV1nAJK6PEwh --cookie-file cookie.txt
    python main.py https://www.bilibili.com/video/BV1nAJK6PEwh/
    python main.py BV1nAJK6PEwh --export-only
    python main.py BV1nAJK6PEwh --restart
"""
import argparse
import os
import sys
from pathlib import Path

from bili_stats.collectors import CommentCollector, DanmakuCollector
from bili_stats.client import AdaptiveLimiter, BilibiliClient
from bili_stats.models import ParsedInput
from bili_stats.resolver import Resolver
from bili_stats.storage import Repository, export, migrate_database, resolve_database_path
from bili_stats.utils.input import InputKind, parse_input
from bili_stats.utils.progress import ProgressReporter


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="B站弹幕与评论统计工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s BV1nAJK6PEwh --cookie-file cookie.txt
  %(prog)s https://www.bilibili.com/video/BV1nAJK6PEwh/
  %(prog)s BV1nAJK6PEwh --export-only
  %(prog)s BV1nAJK6PEwh --restart --max-attempts 10
        """
    )

    parser.add_argument(
        "input",
        help="B站视频URL、BV号、ep/ss号或合集URL"
    )

    cookie_group = parser.add_mutually_exclusive_group()
    cookie_group.add_argument(
        "--cookie",
        help="登录Cookie字符串"
    )
    cookie_group.add_argument(
        "--cookie-file",
        type=Path,
        help="Cookie文件路径"
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="数据库文件路径（默认自动创建）"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Results"),
        help="输出目录（默认: Results）"
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--restart",
        action="store_true",
        help="重新开始任务，清除已有进度"
    )
    mode_group.add_argument(
        "--export-only",
        action="store_true",
        help="仅导出已有数据，不获取新数据"
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="请求失败最大重试次数（默认: 5）"
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.05,
        help="最小请求间隔秒数（默认: 0.05）"
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="最大并发数（默认: 6）"
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="关闭动态进度条"
    )

    return parser


def get_work_key(parsed: ParsedInput) -> str:
    """生成作品标识"""
    if parsed.kind == InputKind.VIDEO:
        return f"video:{parsed.identifier}"
    if parsed.kind == InputKind.SEASON:
        return f"season:{parsed.identifier}"
    if parsed.kind == InputKind.COLLECTION:
        return f"collection:{parsed.owner_mid}:{parsed.identifier}"
    raise ValueError("ep 输入无法离线确定季度，请使用 ss 输入导出")


def main(argv=None) -> int:
    """主函数"""
    args = create_parser().parse_args(argv)

    # 解析输入
    parsed = parse_input(args.input)
    progress = ProgressReporter(enabled=not args.no_progress)
    repository = None

    try:
        # 仅导出模式
        if args.export_only:
            key = get_work_key(parsed)
            database_path = args.database or _discover_database(args.output_dir, key)
            repository = Repository(database_path)
            repository.initialize()
            print(f"数据库: {database_path}")
            print(f"输出: {export(repository, key, args.output_dir, progress=progress)}")
            return 0

        # 获取Cookie
        cookie = args.cookie or (
            args.cookie_file.read_text(encoding="utf-8").strip()
            if args.cookie_file
            else os.environ.get("BILIBILI_COOKIE")
        )

        # 初始化客户端
        limiter = AdaptiveLimiter(
            initial_concurrency=args.concurrency,
            max_concurrency=max(args.concurrency, 8),
            min_delay=args.request_delay,
        )
        client = BilibiliClient(cookie, args.max_attempts, limiter)

        # 解析视频信息
        work = Resolver(client).resolve(parsed)

        # 初始化数据库
        database_path = args.database or resolve_database_path(args.database, args.output_dir, work.title)

        # 迁移旧数据库
        if database_path.exists():
            migrated = migrate_database(database_path)
            if migrated:
                print(f"已迁移数据库: {database_path}")

        repository = Repository(database_path)
        repository.initialize()
        print(f"数据库: {database_path}")

        # 重启模式
        if args.restart:
            repository.restart_work(work.work_key)

        # 保存作品信息
        repository.upsert_work(work.work_key, work.kind, work.title, source=work.source)
        for episode in work.episodes:
            repository.upsert_episode(
                work.work_key,
                episode.episode_key,
                episode.position,
                episode.title,
                episode.bvid,
                episode.aid,
                episode.cid,
                episode.ep_id,
            )

        # 收集弹幕
        failures = 0
        danmaku = DanmakuCollector(client, repository, progress)
        comments = CommentCollector(client, repository, progress)

        for episode in work.episodes:
            try:
                print(f"弹幕: {episode.title}", flush=True)
                danmaku.collect(episode)
            except Exception as error:
                failures += 1
                repository.record_failure(work.work_key, episode.episode_key, "danmaku", error)
                print(f"失败: {error}")

        # 收集评论
        for aid in dict.fromkeys(episode.aid for episode in work.episodes):
            try:
                print(f"评论: {aid}", flush=True)
                comments.collect(work.work_key, aid)
            except Exception as error:
                failures += 1
                repository.record_failure(work.work_key, None, "comments", error)
                print(f"失败: {error}")

        # 导出Excel
        print(f"输出: {export(repository, work.work_key, args.output_dir, progress=progress)}")
        return 0 if failures == 0 else 2

    except KeyboardInterrupt:
        print("已中断，进度已保存")
        return 130

    finally:
        if repository is not None:
            repository.close()


if __name__ == "__main__":
    sys.exit(main())
