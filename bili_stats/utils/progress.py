"""进度报告"""
import sys
import time
from contextlib import contextmanager


class ProgressTask:
    """进度任务"""

    def __init__(self, description: str, total: int = None, initial: int = 0, unit: str = ""):
        self.description = description
        self.total = total
        self.unit = unit
        self.current = initial
        self.start_time = time.time()
        self._last_print = 0

    def update(self, n: int = 1, **extra):
        """更新进度"""
        self.current += n
        now = time.time()

        # 每0.5秒更新一次显示
        if now - self._last_print >= 0.5:
            self._display(extra)
            self._last_print = now

    def _display(self, extra: dict = None):
        """显示进度"""
        elapsed = time.time() - self.start_time
        parts = [f"\r{self.description}: {self.current}"]

        if self.total:
            percent = self.current / self.total * 100
            parts.append(f"/{self.total} ({percent:.1f}%)")

        if self.unit:
            parts.append(f" {self.unit}")

        if elapsed > 0 and self.current > 0:
            speed = self.current / elapsed
            parts.append(f" [{speed:.1f}/s]")

        if extra:
            for key, value in extra.items():
                parts.append(f" {key}={value}")

        sys.stdout.write("".join(parts) + " ")
        sys.stdout.flush()

    def finish(self):
        """完成任务"""
        elapsed = time.time() - self.start_time
        print(f"\r{self.description}: 完成 ({self.current} {self.unit}, {elapsed:.1f}s)")


class ProgressReporter:
    """进度报告器"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @contextmanager
    def task(self, description: str, total: int = None, initial: int = 0, unit: str = ""):
        """创建进度任务上下文"""
        if not self.enabled:
            yield None
            return

        task = ProgressTask(description, total, initial, unit)
        try:
            yield task
        finally:
            task.finish()


# 空进度报告器（用于禁用进度时）
class NullProgress:
    """空进度报告器"""

    @contextmanager
    def task(self, description: str, total: int = None, unit: str = ""):
        yield None


NULL_PROGRESS = NullProgress()
