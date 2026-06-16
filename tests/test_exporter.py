"""测试Excel导出"""
import pytest
import pandas as pd
from pathlib import Path
from bili_stats.storage.exporter import (
    build_comment_user_rows,
    build_danmaku_user_rows,
    excel_cell,
    excel_text,
    safe_name,
)


class TestExcelUtils:
    """测试Excel工具函数"""

    def test_excel_text_short(self):
        """测试短文本"""
        result = excel_text(["hello", "world"])
        assert result == "hello\nworld"

    def test_excel_text_long(self):
        """测试长文本截断"""
        long_text = "x" * 40000
        result = excel_text([long_text])
        assert len(result) <= 32767
        assert result.endswith("...[内容已截断]")

    def test_excel_cell_clean(self):
        """测试单元格清理"""
        result = excel_cell("hello\x00world")
        assert "\x00" not in result
        assert result == "helloworld"

    def test_excel_cell_non_string(self):
        """测试非字符串值"""
        assert excel_cell(123) == 123
        assert excel_cell(None) is None

    def test_safe_name(self):
        """测试安全文件名"""
        assert safe_name("test/video") == "test_video"
        assert safe_name('test:*?"<>|video') == "test______video"
        assert safe_name("") == "未命名"
        assert safe_name("   .") == "未命名"


class TestBuildRows:
    """测试构建行函数"""

    def test_build_danmaku_user_rows(self):
        """测试弹幕用户排行"""
        rows = [
            {"sender_hash": "user1", "content": "弹幕1"},
            {"sender_hash": "user1", "content": "弹幕2"},
            {"sender_hash": "user2", "content": "弹幕3"},
        ]
        result = build_danmaku_user_rows(rows)
        assert len(result) == 2
        assert result[0]["排名"] == 1
        assert result[0]["弹幕次数"] == 2  # user1有2条
        assert result[1]["弹幕次数"] == 1  # user2有1条

    def test_build_comment_user_rows(self):
        """测试评论用户排行"""
        rows = [
            {"user_mid": "123", "user_name": "用户A", "content": "评论1", "ctime": 100},
            {"user_mid": "123", "user_name": "用户A", "content": "评论2", "ctime": 200},
            {"user_mid": "456", "user_name": "用户B", "content": "评论3", "ctime": 150},
        ]
        result = build_comment_user_rows(rows)
        assert len(result) == 2
        assert result[0]["排名"] == 1
        assert result[0]["评论次数"] == 2  # 用户A有2条
        assert result[0]["用户名"] == "用户A"
