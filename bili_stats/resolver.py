"""解析器 - 解析视频信息，获取剧集列表"""
from typing import Dict, List

from .models import Episode, Work
from .utils.input import InputKind


class Resolver:
    """视频信息解析器"""

    def __init__(self, client):
        self.client = client

    def resolve(self, parsed) -> Work:
        """
        解析输入，获取作品信息

        Args:
            parsed: 解析后的输入

        Returns:
            作品对象
        """
        if parsed.kind == InputKind.VIDEO:
            return self._resolve_video(parsed)
        if parsed.kind == InputKind.SEASON:
            return self._resolve_season(parsed)
        if parsed.kind == InputKind.COLLECTION:
            return self._resolve_collection(parsed)
        if parsed.kind == InputKind.EPISODE:
            return self._resolve_episode(parsed)
        raise ValueError(f"不支持的输入类型: {parsed.kind}")

    def _resolve_video(self, parsed) -> Work:
        """解析单个视频"""
        data = self.client.get_json(
            f"https://api.bilibili.com/x/web-interface/view",
            {"bvid": parsed.identifier}
        )

        # 如果指定了分P，只获取该分P
        if parsed.page:
            pages = data.get("pages") or []
            page_data = None
            for page in pages:
                if page.get("page") == parsed.page:
                    page_data = page
                    break

            if not page_data:
                raise ValueError(f"分P {parsed.page} 不存在")

            episode = Episode(
                episode_key=f"{data['bvid']}_p{parsed.page}",
                position=parsed.page,
                title=page_data.get("part", f"P{parsed.page}"),
                bvid=data["bvid"],
                aid=data["aid"],
                cid=page_data["cid"],
            )

            return Work(
                work_key=f"video:{data['bvid']}",
                kind="video",
                title=data.get("title", ""),
                episodes=[episode],
                source=data,
            )

        # 获取所有分P
        pages = data.get("pages") or []
        if not pages:
            # 单P视频
            episode = Episode(
                episode_key=data["bvid"],
                position=1,
                title=data.get("title", ""),
                bvid=data["bvid"],
                aid=data["aid"],
                cid=data["cid"],
            )
            episodes = [episode]
        else:
            # 多P视频
            episodes = [
                Episode(
                    episode_key=f"{data['bvid']}_p{page.get('page', i+1)}",
                    position=page.get("page", i + 1),
                    title=page.get("part", f"P{page.get('page', i+1)}"),
                    bvid=data["bvid"],
                    aid=data["aid"],
                    cid=page["cid"],
                )
                for i, page in enumerate(pages)
            ]

        return Work(
            work_key=f"video:{data['bvid']}",
            kind="video",
            title=data.get("title", ""),
            episodes=episodes,
            source=data,
        )

    def _resolve_season(self, parsed) -> Work:
        """解析番剧季度"""
        data = self.client.get_json(
            "https://api.bilibili.com/pgc/web/season/section",
            {"season_id": parsed.identifier}
        )

        season_info = data.get("main_section") or {}
        episodes_data = season_info.get("episodes") or []

        episodes = [
            Episode(
                episode_key=f"ep{ep.get('ep_id', i+1)}",
                position=ep.get("title", str(i + 1)),
                title=ep.get("share_copy", ep.get("long_title", f"第{i+1}集")),
                bvid=ep.get("bvid", ""),
                aid=ep.get("aid", 0),
                cid=ep.get("cid", 0),
                ep_id=ep.get("ep_id"),
            )
            for i, ep in enumerate(episodes_data)
        ]

        # 获取季度信息
        season_info = self.client.get_json(
            "https://api.bilibili.com/pgc/view/web/season",
            {"season_id": parsed.identifier}
        )

        return Work(
            work_key=f"season:{parsed.identifier}",
            kind="season",
            title=season_info.get("title", f"季度{parsed.identifier}"),
            episodes=episodes,
            source_id=parsed.identifier,
            source=season_info,
        )

    def _resolve_collection(self, parsed) -> Work:
        """解析合集"""
        data = self.client.get_json(
            f"https://api.bilibili.com/polymer/web-space/seasons_archives_list",
            {
                "mid": parsed.owner_mid,
                "season_id": parsed.identifier,
                "sort_reverse": "false",
                "page_num": 1,
                "page_size": 100,
            }
        )

        archives = data.get("archives") or []
        meta = data.get("meta") or {}

        episodes = [
            Episode(
                episode_key=arc.get("bvid", f"av{arc.get('aid', i+1)}"),
                position=i + 1,
                title=arc.get("title", f"视频{i+1}"),
                bvid=arc.get("bvid", ""),
                aid=arc.get("aid", 0),
                cid=arc.get("cid", 0),
            )
            for i, arc in enumerate(archives)
        ]

        return Work(
            work_key=f"collection:{parsed.owner_mid}:{parsed.identifier}",
            kind="collection",
            title=meta.get("name", f"合集{parsed.identifier}"),
            episodes=episodes,
            owner_mid=parsed.owner_mid,
            source_id=parsed.identifier,
            source=meta,
        )

    def _resolve_episode(self, parsed) -> Work:
        """解析单集"""
        data = self.client.get_json(
            "https://api.bilibili.com/pgc/view/web/season",
            {"ep_id": parsed.identifier}
        )

        episodes_data = data.get("episodes") or []

        # 找到对应的单集
        target_ep = None
        for ep in episodes_data:
            if str(ep.get("ep_id")) == parsed.identifier:
                target_ep = ep
                break

        if not target_ep:
            raise ValueError(f"找不到剧集 ep{parsed.identifier}")

        episode = Episode(
            episode_key=f"ep{parsed.identifier}",
            position=1,
            title=target_ep.get("share_copy", target_ep.get("long_title", f"ep{parsed.identifier}")),
            bvid=target_ep.get("bvid", ""),
            aid=target_ep.get("aid", 0),
            cid=target_ep.get("cid", 0),
            ep_id=int(parsed.identifier),
        )

        return Work(
            work_key=f"episode:{parsed.identifier}",
            kind="episode",
            title=episode.title,
            episodes=[episode],
            source=data,
        )
