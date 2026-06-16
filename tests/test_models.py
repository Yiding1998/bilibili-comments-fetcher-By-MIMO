"""测试数据模型"""
import pytest
from bili_stats.models import Comment, Danmaku, Episode, ParsedInput, Work


class TestParsedInput:
    """测试ParsedInput模型"""

    def test_create(self):
        """测试创建"""
        parsed = ParsedInput(kind="video", identifier="BV123", original="BV123")
        assert parsed.kind == "video"
        assert parsed.identifier == "BV123"

    def test_immutable(self):
        """测试不可变性"""
        parsed = ParsedInput(kind="video", identifier="BV123")
        with pytest.raises(AttributeError):
            parsed.kind = "other"


class TestEpisode:
    """测试Episode模型"""

    def test_create(self):
        """测试创建"""
        episode = Episode(
            episode_key="BV123_p1",
            position=1,
            title="第一P",
            bvid="BV123",
            aid=111,
            cid=222
        )
        assert episode.episode_key == "BV123_p1"
        assert episode.position == 1


class TestWork:
    """测试Work模型"""

    def test_create(self):
        """测试创建"""
        work = Work(
            work_key="video:BV123",
            kind="video",
            title="测试视频"
        )
        assert work.work_key == "video:BV123"
        assert len(work.episodes) == 0

    def test_with_episodes(self):
        """测试带剧集创建"""
        episode = Episode(
            episode_key="BV123_p1",
            position=1,
            title="第一P",
            bvid="BV123",
            aid=111,
            cid=222
        )
        work = Work(
            work_key="video:BV123",
            kind="video",
            title="测试视频",
            episodes=[episode]
        )
        assert len(work.episodes) == 1


class TestDanmaku:
    """测试Danmaku模型"""

    def test_create(self):
        """测试创建"""
        danmaku = Danmaku(
            danmaku_id="1",
            episode_key="BV123_p1",
            content="测试弹幕",
            ctime=1234567890,
            progress=1000,
            fontsize=25,
            color=16777215,
            sender_hash="abc",
            pool=0
        )
        assert danmaku.content == "测试弹幕"
        assert danmaku.mode == 1  # 默认值


class TestComment:
    """测试Comment模型"""

    def test_create(self):
        """测试创建"""
        comment = Comment(
            rpid="123",
            work_key="video:BV123",
            aid=111,
            user_mid="456",
            user_name="测试用户",
            content="测试评论"
        )
        assert comment.content == "测试评论"
        assert comment.likes == 0  # 默认值
