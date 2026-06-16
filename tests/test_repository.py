"""测试数据库仓库"""
import pytest
import tempfile
from pathlib import Path
from bili_stats.storage.repository import Repository
from bili_stats.models import Danmaku, Comment


@pytest.fixture
def db_path(tmp_path):
    """创建临时数据库路径"""
    return tmp_path / "test.db"


@pytest.fixture
def repository(db_path):
    """创建测试用仓库"""
    repo = Repository(db_path)
    repo.initialize()
    yield repo
    repo.close()


class TestRepository:
    """测试Repository类"""

    def test_initialize(self, repository):
        """测试初始化"""
        # 检查表是否存在
        result = repository.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [row[0] for row in result]
        assert "works" in table_names
        assert "episodes" in table_names
        assert "danmaku" in table_names
        assert "comments" in table_names

    def test_upsert_work(self, repository):
        """测试插入/更新作品"""
        repository.upsert_work("video:BV123", "video", "测试视频", {"stat": {"view": 100}})
        work = repository.get_work("video:BV123")
        assert work is not None
        assert work["title"] == "测试视频"
        assert work["kind"] == "video"

    def test_upsert_work_update(self, repository):
        """测试更新作品"""
        repository.upsert_work("video:BV123", "video", "原标题")
        repository.upsert_work("video:BV123", "video", "新标题")
        work = repository.get_work("video:BV123")
        assert work["title"] == "新标题"

    def test_upsert_episode(self, repository):
        """测试插入剧集"""
        repository.upsert_work("video:BV123", "video", "测试视频")
        repository.upsert_episode("video:BV123", "BV123_p1", 1, "第一P", "BV123", 111, 222)
        episodes = repository.list_episodes("video:BV123")
        assert len(episodes) == 1
        assert episodes[0]["title"] == "第一P"

    def test_danmaku_progress(self, repository):
        """测试弹幕进度"""
        repository.upsert_work("video:BV123", "video", "测试视频")
        repository.upsert_episode("video:BV123", "BV123_p1", 1, "第一P", "BV123", 111, 222)

        # 初始状态
        assert repository.get_danmaku_next_segment("BV123_p1") == 1

        # 设置总数
        repository.set_danmaku_total("BV123_p1", 100)

        # 提交分段
        item = Danmaku(
            danmaku_id="1", episode_key="BV123_p1", content="测试弹幕",
            ctime=1234567890, progress=1000, fontsize=25, color=16777215,
            sender_hash="abc123", pool=0
        )
        repository.commit_danmaku_segment("BV123_p1", 1, [item], False)
        assert repository.count_danmaku("BV123_p1") == 1
        assert repository.get_danmaku_next_segment("BV123_p1") == 2

    def test_comment_progress(self, repository):
        """测试评论进度"""
        repository.upsert_work("video:BV123", "video", "测试视频")

        # 初始状态
        state = repository.get_comment_progress("video:BV123", 111)
        assert state["next_cursor"] == ""
        assert state["complete"] is False

        # 提交评论
        comment = Comment(
            rpid="123", work_key="video:BV123", aid=111,
            user_mid="456", user_name="测试用户", content="测试评论"
        )
        repository.commit_comment_page("video:BV123", 111, [comment], "cursor123", False)
        assert repository.count_comments("video:BV123") == 1

    def test_restart_work(self, repository):
        """测试重启任务"""
        repository.upsert_work("video:BV123", "video", "测试视频")
        repository.restart_work("video:BV123")
        assert repository.get_work("video:BV123") is None

    def test_record_failure(self, repository):
        """测试记录失败"""
        repository.record_failure("video:BV123", "BV123_p1", "danmaku", Exception("测试错误"))
        # 不抛出异常即为成功
