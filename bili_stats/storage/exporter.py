"""Excel导出 - 生成统计报表"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..utils.progress import NULL_PROGRESS

# Excel单元格限制
EXCEL_CELL_LIMIT = 32767
TRUNCATION_MARKER = "...[内容已截断]"
UNKNOWN_IDENTITY = "(未知)"
INVALID_EXCEL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def excel_text(parts: list) -> str:
    """组合文本，处理长度限制"""
    text = "\n".join("" if part is None else str(part) for part in parts)
    if len(text) <= EXCEL_CELL_LIMIT:
        return text
    return text[: EXCEL_CELL_LIMIT - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def excel_cell(value) -> str:
    """清理Excel单元格内容"""
    if not isinstance(value, str):
        return value
    return excel_text([INVALID_EXCEL_CHARS.sub("", value)])


def safe_name(value: str) -> str:
    """生成安全的文件名"""
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value)).strip(" .")
    return value[:120] or "未命名"


def build_danmaku_user_rows(rows: List[Dict]) -> List[Dict]:
    """构建弹幕用户排行"""
    groups = defaultdict(list)
    for row in rows:
        identity = str(row.get("sender_hash") or UNKNOWN_IDENTITY)
        groups[identity].append(row.get("content", ""))

    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))

    return [
        {
            "排名": rank,
            "发送者标识": identity,
            "发送者哈希": identity,
            "弹幕次数": len(contents),
            "弹幕内容": excel_text(contents),
        }
        for rank, (identity, contents) in enumerate(ordered, 1)
    ]


def build_comment_user_rows(rows: List[Dict]) -> List[Dict]:
    """构建评论用户排行"""
    groups = defaultdict(list)
    names = defaultdict(list)

    for index, row in enumerate(rows):
        identity = str(row.get("user_mid") or UNKNOWN_IDENTITY)
        groups[identity].append(row.get("content", ""))
        name = str(row.get("user_name") or "")
        if name:
            names[identity].append((int(row.get("ctime") or 0), index, name))

    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))

    result = []
    for rank, (identity, contents) in enumerate(ordered, 1):
        result.append({
            "排名": rank,
            "用户MID": identity,
            "用户名": max(names.get(identity, [(0, 0, UNKNOWN_IDENTITY)]))[2],
            "评论次数": len(contents),
            "评论内容": excel_text(contents),
        })

    return result


def build_video_info_rows(work: Dict, episodes: List[Dict], danmaku_rows: List[Dict], comment_rows: List[Dict]) -> List[Dict]:
    """构建视频信息"""
    try:
        source = json.loads(work.get("source_json") or "{}")
    except (TypeError, ValueError):
        source = {}

    stat = source.get("stat") or {}
    owner = source.get("owner") or {}
    first_episode = episodes[0] if episodes else {}

    def value(mapping, key, fallback=""):
        result = mapping.get(key)
        return fallback if result is None else result

    return [{
        "视频标题": value(source, "title", work.get("title", "")),
        "BVID": value(source, "bvid", first_episode.get("bvid", "")),
        "AID": value(source, "aid", first_episode.get("aid", "")),
        "作者MID": value(owner, "mid"),
        "作者名称": value(owner, "name"),
        "作者头像": value(owner, "face"),
        "播放量": value(stat, "view"),
        "点赞数": value(stat, "like"),
        "投币数": value(stat, "coin"),
        "收藏量": value(stat, "favorite"),
        "转发数": value(stat, "share"),
        "弹幕数": value(stat, "danmaku", len(danmaku_rows)),
        "评论数": value(stat, "reply", len(comment_rows)),
        "视频简介": value(source, "desc"),
    }]


def _write_excel(path: Path, rows: List[Dict]):
    """写入Excel文件"""
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.applymap(excel_cell)
    frame.to_excel(str(path), index=False, engine="openpyxl")


def export(repository, work_key: str, output_root: str, progress=None) -> Path:
    """
    导出Excel报表

    Args:
        repository: 数据库仓库
        work_key: 作品标识
        output_root: 输出根目录
        progress: 进度报告器

    Returns:
        输出目录路径
    """
    work = repository.get_work(work_key)
    if not work:
        raise ValueError(f"数据库中不存在任务 {work_key}")

    root = Path(output_root) / safe_name(work["title"])
    root.mkdir(parents=True, exist_ok=True)

    episodes = repository.list_episodes(work_key)
    all_danmaku = repository.list_danmaku(work_key)
    comments = repository.list_comments(work_key)

    reporter = progress or NULL_PROGRESS
    total_files = len(episodes) * 5 + 6

    with reporter.task("导出 Excel", total=total_files, unit="文件") as task:
        def write(path, rows):
            _write_excel(path, rows)
            if task:
                task.update()

        # 每个剧集单独导出
        for episode in episodes:
            folder = root / f"{episode['position']:02d}-{safe_name(episode['title'])}"
            folder.mkdir(parents=True, exist_ok=True)

            rows = [row for row in all_danmaku if row["episode_key"] == episode["episode_key"]]

            # 弹幕明细
            write(folder / "弹幕明细.xlsx", rows)

            # 弹幕统计
            write(folder / "弹幕统计.xlsx", [
                {"弹幕内容": key, "出现次数": value}
                for key, value in Counter(row["content"] for row in rows).most_common()
            ])

            # 弹幕用户排行
            write(folder / "弹幕用户排行.xlsx", build_danmaku_user_rows(rows))

            # 完整评论
            write(folder / "完整评论.xlsx", comments)

            # 评论用户统计
            write(folder / "评论用户统计.xlsx", [
                {"用户名": key, "评论次数": value}
                for key, value in Counter(row["user_name"] for row in comments).most_common()
            ])

        # 全局统计
        write(root / "视频信息.xlsx", build_video_info_rows(work, episodes, all_danmaku, comments))

        write(root / "全局弹幕统计.xlsx", [
            {"弹幕内容": key, "出现次数": value}
            for key, value in Counter(row["content"] for row in all_danmaku).most_common()
        ])

        write(root / "全局弹幕用户排行.xlsx", build_danmaku_user_rows(all_danmaku))

        write(root / "全局评论统计.xlsx", [
            {"用户名": key, "评论次数": value}
            for key, value in Counter(row["user_name"] for row in comments).most_common()
        ])

        write(root / "评论用户排行.xlsx", build_comment_user_rows(comments))

        write(root / "分集概览.xlsx", [
            {
                "序号": episode["position"],
                "标题": episode["title"],
                "BVID": episode["bvid"],
                "CID": episode["cid"],
                "弹幕条数": sum(1 for row in all_danmaku if row["episode_key"] == episode["episode_key"]),
            }
            for episode in episodes
        ])

    return root
