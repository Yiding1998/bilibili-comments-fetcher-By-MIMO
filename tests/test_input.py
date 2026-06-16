"""测试输入解析"""
import pytest
from bili_stats.utils.input import InputKind, parse_input


class TestParseInput:
    """测试parse_input函数"""

    def test_bvid(self):
        """测试BV号解析"""
        result = parse_input("BV1nAJK6PEwh")
        assert result.kind == InputKind.VIDEO
        assert result.identifier == "BV1nAJK6PEwh"
        assert result.original == "BV1nAJK6PEwh"

    def test_bvid_url(self):
        """测试BV号URL解析"""
        result = parse_input("https://www.bilibili.com/video/BV1nAJK6PEwh/")
        assert result.kind == InputKind.VIDEO
        assert result.identifier == "BV1nAJK6PEwh"

    def test_bvid_url_with_page(self):
        """测试带分P的URL解析"""
        result = parse_input("https://www.bilibili.com/video/BV1nAJK6PEwh/?p=2")
        assert result.kind == InputKind.VIDEO
        assert result.identifier == "BV1nAJK6PEwh"
        assert result.page == 2

    def test_episode(self):
        """测试ep号解析"""
        result = parse_input("ep12345")
        assert result.kind == InputKind.EPISODE
        assert result.identifier == "12345"

    def test_season(self):
        """测试ss号解析"""
        result = parse_input("ss67890")
        assert result.kind == InputKind.SEASON
        assert result.identifier == "67890"

    def test_bangumi_url(self):
        """测试番剧URL解析"""
        result = parse_input("https://www.bilibili.com/bangumi/play/ep12345")
        assert result.kind == InputKind.EPISODE
        assert result.identifier == "12345"

    def test_collection_url(self):
        """测试合集URL解析"""
        result = parse_input("https://space.bilibili.com/123456/lists/789?type=season")
        assert result.kind == InputKind.COLLECTION
        assert result.identifier == "789"
        assert result.owner_mid == "123456"

    def test_invalid_input(self):
        """测试无效输入"""
        with pytest.raises(ValueError):
            parse_input("")

    def test_invalid_url(self):
        """测试无效URL"""
        with pytest.raises(ValueError):
            parse_input("https://example.com/video/test")

    def test_non_string_input(self):
        """测试非字符串输入"""
        with pytest.raises(ValueError):
            parse_input(123)
