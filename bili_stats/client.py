"""HTTP客户端 - Wbi签名、自适应限流、自动重试"""
import hashlib
import random
import threading
import time
from functools import reduce
from urllib.parse import urlencode
from typing import Any

import requests


# Wbi签名混淆表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def encode_wbi(params: dict, img_key: str, sub_key: str, timestamp: int = None) -> dict:
    """
    Wbi签名算法

    Args:
        params: 请求参数
        img_key: Wbi图片密钥
        sub_key: Wbi子密钥
        timestamp: 时间戳（可选）

    Returns:
        添加了签名的参数字典
    """
    source = dict(params)
    source["wts"] = int(time.time() if timestamp is None else timestamp)

    # 过滤特殊字符
    source = {
        key: "".join(ch for ch in str(value) if ch not in "!'()*")
        for key, value in source.items()
    }

    # 生成混淆密钥
    mixin = reduce(lambda value, index: value + (img_key + sub_key)[index], MIXIN_KEY_ENC_TAB, "")[:32]

    # 计算签名
    query = urlencode(sorted(source.items()))
    source["w_rid"] = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
    source["wts"] = int(source["wts"])

    return source


class AdaptiveLimiter:
    """自适应限流器 - 动态调整并发和请求间隔"""

    def __init__(
        self,
        initial_concurrency: int = 6,
        max_concurrency: int = 8,
        min_delay: float = 0.05,
        recovery_successes: int = 20,
    ):
        self.max_concurrency = max(1, max_concurrency)
        self.concurrency = min(max(1, initial_concurrency), self.max_concurrency)
        self.min_delay = max(0.0, min_delay)
        self.recovery_successes = max(1, recovery_successes)

        self._successes = 0
        self._last_request = 0.0
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active = 0

    def acquire(self):
        """获取并发槽位"""
        with self._condition:
            while self._active >= self.concurrency:
                self._condition.wait()
            self._active += 1

    def release(self):
        """释放并发槽位"""
        with self._condition:
            self._active -= 1
            self._condition.notify_all()

    def wait(self):
        """等待请求间隔"""
        with self._lock:
            delay = self.min_delay - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()

    def record_throttle(self):
        """记录被限流，降低并发"""
        with self._lock:
            self.concurrency = max(1, self.concurrency // 2)
            self.min_delay = min(5.0, max(0.2, self.min_delay * 2))
            self._successes = 0

    def record_success(self):
        """记录成功请求，逐步恢复"""
        with self._lock:
            self._successes += 1
            if self._successes >= self.recovery_successes:
                self.concurrency = min(self.max_concurrency, self.concurrency + 1)
                self.min_delay = max(0.05, self.min_delay * 0.8)
                self._successes = 0


class BilibiliError(RuntimeError):
    """B站API错误"""
    pass


class BilibiliClient:
    """B站HTTP客户端"""

    def __init__(self, cookie: str = None, max_attempts: int = 5, limiter: AdaptiveLimiter = None, session: requests.Session = None):
        self.max_attempts = max_attempts
        self.limiter = limiter or AdaptiveLimiter()
        self.session = session or requests.Session()

        # 设置请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        })

        if cookie:
            self.session.headers["Cookie"] = cookie

        self._wbi_keys = None

    def _request(self, url: str, params: dict = None, binary: bool = False) -> Any:
        """发送请求，带重试和限流"""
        last_error = None

        for attempt in range(self.max_attempts):
            self.limiter.acquire()
            try:
                self.limiter.wait()
                response = self.session.get(url, params=params, timeout=20)

                # 处理限流响应
                if response.status_code in (412, 429) or response.status_code >= 500:
                    self.limiter.record_throttle()
                    raise BilibiliError(f"temporary HTTP {response.status_code}")

                response.raise_for_status()
                payload = response.content if binary else response.json()

                # 处理API限流
                if not binary and payload.get("code") in (-412, -429):
                    self.limiter.record_throttle()
                    raise BilibiliError(f"temporary API {payload.get('code')}")

                self.limiter.record_success()
                return payload

            except (requests.RequestException, ValueError, BilibiliError) as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    break
                # 指数退避
                time.sleep(min(30.0, (2 ** attempt) + random.random()))

            finally:
                self.limiter.release()

        raise BilibiliError(f"request failed: {last_error}")

    def get_json(self, url: str, params: dict = None, signed: bool = False) -> dict:
        """获取JSON响应"""
        if signed:
            img, sub = self.get_wbi_keys()
            params = encode_wbi(params or {}, img, sub)

        data = self._request(url, params=params)

        if data.get("code") != 0:
            raise BilibiliError(f"API {data.get('code')}: {data.get('message', 'unknown')}")

        return data.get("data") or {}

    def get_bytes(self, url: str, params: dict = None) -> bytes:
        """获取二进制响应"""
        return self._request(url, params=params, binary=True)

    def get_wbi_keys(self) -> tuple:
        """获取Wbi签名密钥"""
        if self._wbi_keys:
            return self._wbi_keys

        data = self.get_json("https://api.bilibili.com/x/web-interface/nav")
        images = data["wbi_img"]

        # 从URL中提取密钥
        self._wbi_keys = tuple(
            url.rsplit("/", 1)[-1].split(".", 1)[0]
            for url in (images["img_url"], images["sub_url"])
        )

        return self._wbi_keys
