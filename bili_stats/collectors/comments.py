"""评论收集器 - 支持主评论和子评论"""
import json
from concurrent.futures import ThreadPoolExecutor

from ..models import Comment
from ..utils.progress import NULL_PROGRESS


class CommentCollector:
    """评论收集器"""

    MAIN_URL = "https://api.bilibili.com/x/v2/reply/wbi/main"
    CHILD_URL = "https://api.bilibili.com/x/v2/reply/reply"

    def __init__(self, client, repository, progress=None):
        self.client = client
        self.repository = repository
        self.progress = progress or NULL_PROGRESS

    def _parse_comment(self, raw: dict, work_key: str, aid: int, root: str = None) -> Comment:
        """解析单条评论"""
        return Comment(
            rpid=str(raw["rpid"]),
            work_key=work_key,
            aid=aid,
            user_mid=str(raw.get("mid") or raw.get("member", {}).get("mid", "")),
            user_name=raw.get("member", {}).get("uname", ""),
            content=raw.get("content", {}).get("message", ""),
            root_rpid=str(raw.get("root") or root or "") or None,
            parent_rpid=str(raw.get("parent") or "") or None,
            ctime=int(raw.get("ctime", 0)),
            likes=int(raw.get("like", 0)),
        )

    def collect(self, work_key: str, aid: int) -> int:
        """
        收集评论

        Args:
            work_key: 作品标识
            aid: 视频aid

        Returns:
            评论总数
        """
        # 获取上次中断的位置
        state = self.repository.get_comment_progress(work_key, aid)
        cursor = state["next_cursor"]
        roots = set()

        # 收集主评论
        with self.progress.task(f"主评论 aid={aid}", unit="页") as task:
            while not state["complete"]:
                params = {"type": 1, "oid": aid, "mode": 3, "plat": 1}
                if cursor:
                    params["pagination_str"] = json.dumps({"offset": cursor}, separators=(",", ":"))

                # 使用Wbi签名
                data = self.client.get_json(self.MAIN_URL, params, signed=True)

                comments = []
                for raw in data.get("replies") or []:
                    root = self._parse_comment(raw, work_key, aid)
                    comments.append(root)

                    # 解析嵌套的子评论
                    embedded = raw.get("replies") or []
                    comments.extend(
                        self._parse_comment(item, work_key, aid, root.rpid)
                        for item in embedded
                    )

                    # 如果有更多子评论，记录需要后续获取
                    if int(raw.get("rcount", 0)) > len(embedded):
                        roots.add(root.rpid)
                        self.repository.commit_child_comment_page(work_key, root.rpid, [], 1, False)

                # 更新分页游标
                page_cursor = data.get("cursor") or {}
                complete = bool(page_cursor.get("is_end"))
                cursor = (page_cursor.get("pagination_reply") or {}).get("next_offset") or ""

                if not complete and not cursor:
                    raise ValueError("主评论分页游标缺失")

                # 保存到数据库
                self.repository.commit_comment_page(work_key, aid, comments, cursor, complete)
                state = {"complete": complete, "next_cursor": cursor}

                if task:
                    task.update(1, records=self.repository.count_comments(work_key))

        # 获取未完成的子评论
        roots.update(self.repository.list_pending_child_roots(work_key, aid))

        with self.progress.task(f"子评论 aid={aid}", total=len(roots), unit="根") as task:
            with ThreadPoolExecutor(max_workers=self.client.limiter.max_concurrency) as pool:
                for _ in pool.map(lambda root: self._collect_children(work_key, aid, root), roots):
                    if task:
                        task.update()

        return self.repository.count_comments(work_key)

    def _collect_children(self, work_key: str, aid: int, root: str):
        """收集子评论"""
        state = self.repository.get_child_progress(work_key, root)
        page = int(state["next_page"])

        while not state["complete"]:
            data = self.client.get_json(
                self.CHILD_URL,
                {"type": 1, "oid": aid, "root": root, "pn": page, "ps": 20}
            )

            replies = data.get("replies") or []
            comments = [self._parse_comment(item, work_key, aid, root) for item in replies]

            info = data.get("page") or {}
            complete = not replies or page * int(info.get("size", 20)) >= int(info.get("count", 0))

            self.repository.commit_child_comment_page(work_key, root, comments, page + 1, complete)
            page += 1
            state = {"complete": complete}
