"""弹幕收集器 - 使用protobuf解析"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models import Danmaku
from ..utils.progress import NULL_PROGRESS

# 导入protobuf生成的类
try:
    from ..proto.dm_pb2 import DmSegMobileReply, DmWebViewReply
except ImportError:
    # 如果protobuf未编译，使用None占位
    DmSegMobileReply = None
    DmWebViewReply = None


def parse_segment(payload: bytes, episode_key: str) -> list:
    """
    解析弹幕分段

    Args:
        payload: protobuf二进制数据
        episode_key: 剧集标识

    Returns:
        弹幕列表
    """
    if DmSegMobileReply is None:
        raise ImportError("protobuf模块未编译，请先编译proto文件")

    reply = DmSegMobileReply()
    reply.ParseFromString(payload)

    return [
        Danmaku(
            danmaku_id=str(e.idStr or e.id),
            episode_key=episode_key,
            content=e.content,
            ctime=e.ctime,
            progress=e.progress,
            fontsize=e.fontsize,
            color=e.color,
            sender_hash=e.midHash,
            pool=e.pool,
            mode=e.mode,
            weight=e.weight,
            action=e.action,
            attr=e.attr,
        )
        for e in reply.elems
    ]


class DanmakuCollector:
    """弹幕收集器"""

    VIEW_URL = "https://api.bilibili.com/x/v2/dm/web/view"
    SEGMENT_URL = "https://api.bilibili.com/x/v2/dm/web/seg.so"

    def __init__(self, client, repository, progress=None):
        self.client = client
        self.repository = repository
        self.progress = progress or NULL_PROGRESS

    def collect(self, episode) -> int:
        """
        收集弹幕

        Args:
            episode: 剧集信息

        Returns:
            弹幕总数
        """
        # 获取弹幕分段信息
        payload = self.client.get_bytes(self.VIEW_URL, {"type": 1, "oid": episode.cid})

        if DmWebViewReply is None:
            raise ImportError("protobuf模块未编译，请先编译proto文件")

        view = DmWebViewReply()
        view.ParseFromString(payload)
        total = int(view.dmSge.total)

        if total < 1:
            raise ValueError("弹幕分段总数缺失")

        # 设置弹幕总数
        self.repository.set_danmaku_total(episode.episode_key, total)

        # 获取上次中断的位置
        start = self.repository.get_danmaku_next_segment(episode.episode_key)

        def fetch(segment):
            """获取单个分段"""
            data = self.client.get_bytes(
                self.SEGMENT_URL,
                {"type": 1, "oid": episode.cid, "segment_index": segment}
            )
            return segment, parse_segment(data, episode.episode_key)

        # 并发获取所有分段
        with self.progress.task(f"弹幕 {episode.title}", total=total, initial=start - 1, unit="段") as task:
            with ThreadPoolExecutor(max_workers=self.client.limiter.max_concurrency) as pool:
                futures = [pool.submit(fetch, s) for s in range(start, total + 1)]

                for future in as_completed(futures):
                    segment, items = future.result()
                    self.repository.commit_danmaku_segment(
                        episode.episode_key, segment, items, segment == total
                    )
                    if task:
                        task.update(1, records=self.repository.count_danmaku(episode.episode_key))

        return self.repository.count_danmaku(episode.episode_key)
