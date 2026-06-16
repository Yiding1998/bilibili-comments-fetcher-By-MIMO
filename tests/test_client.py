"""测试HTTP客户端"""
import pytest
from unittest.mock import MagicMock, patch
from bili_stats.client import AdaptiveLimiter, BilibiliClient, BilibiliError, encode_wbi


class TestAdaptiveLimiter:
    """测试自适应限流器"""

    def test_init(self):
        """测试初始化"""
        limiter = AdaptiveLimiter(initial_concurrency=4, max_concurrency=8)
        assert limiter.concurrency == 4
        assert limiter.max_concurrency == 8

    def test_concurrency_clamped(self):
        """测试并发数限制"""
        limiter = AdaptiveLimiter(initial_concurrency=10, max_concurrency=5)
        assert limiter.concurrency == 5

    def test_record_throttle(self):
        """测试限流记录"""
        limiter = AdaptiveLimiter(initial_concurrency=8, max_concurrency=8)
        limiter.record_throttle()
        assert limiter.concurrency == 4  # 减半

    def test_record_success_recovery(self):
        """测试成功恢复"""
        limiter = AdaptiveLimiter(initial_concurrency=4, max_concurrency=8, recovery_successes=2)
        limiter.record_throttle()
        assert limiter.concurrency == 2

        limiter.record_success()
        limiter.record_success()
        assert limiter.concurrency == 3  # 恢复1


class TestEncodeWbi:
    """测试Wbi签名"""

    def test_encode_wbi(self):
        """测试签名生成"""
        params = {"oid": 123, "type": 1}
        result = encode_wbi(params, "test_img_key", "test_sub_key", timestamp=1234567890)
        assert "wts" in result
        assert "w_rid" in result
        assert result["wts"] == 1234567890

    def test_encode_wbi_filters_chars(self):
        """测试特殊字符过滤"""
        params = {"content": "test!(*value)"}
        result = encode_wbi(params, "key", "key", timestamp=1234567890)
        assert "!" not in result["content"]
        assert "(" not in result["content"]


class TestBilibiliClient:
    """测试B站客户端"""

    def test_init_without_cookie(self):
        """测试无Cookie初始化"""
        client = BilibiliClient()
        assert client.max_attempts == 5
        assert "Cookie" not in client.session.headers

    def test_init_with_cookie(self):
        """测试有Cookie初始化"""
        client = BilibiliClient(cookie="SESSDATA=test")
        assert client.session.headers["Cookie"] == "SESSDATA=test"

    @patch("bili_stats.client.requests.Session.get")
    def test_get_json_success(self, mock_get):
        """测试JSON请求成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "data": {"test": "value"}}
        mock_get.return_value = mock_response

        client = BilibiliClient()
        result = client.get_json("https://api.bilibili.com/test")
        assert result == {"test": "value"}

    @patch("bili_stats.client.requests.Session.get")
    def test_get_json_api_error(self, mock_get):
        """测试API错误"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": -412, "message": "风控"}
        mock_get.return_value = mock_response

        client = BilibiliClient(max_attempts=1)
        with pytest.raises(BilibiliError):
            client.get_json("https://api.bilibili.com/test")

    @patch("bili_stats.client.requests.Session.get")
    def test_get_json_http_error_retry(self, mock_get):
        """测试HTTP错误重试"""
        mock_response = MagicMock()
        mock_response.status_code = 412
        mock_response.raise_for_status.side_effect = Exception("412")
        mock_get.return_value = mock_response

        client = BilibiliClient(max_attempts=2)
        with pytest.raises(BilibiliError):
            client.get_json("https://api.bilibili.com/test")
        assert mock_get.call_count == 2
