"""数据库迁移 - 处理旧版本数据库升级"""
import sqlite3
from pathlib import Path
from typing import List


# 当前数据库版本
CURRENT_VERSION = 1


def migrate_database(db_path: Path) -> bool:
    """
    迁移数据库到最新版本

    Args:
        db_path: 数据库文件路径

    Returns:
        是否进行了迁移
    """
    if not db_path.exists():
        return False

    conn = sqlite3.connect(str(db_path))
    try:
        # 获取当前版本
        version = _get_version(conn)

        if version < CURRENT_VERSION:
            # 执行迁移
            migrations = _get_migrations(version)
            for migration in migrations:
                migration(conn)
            _set_version(conn, CURRENT_VERSION)
            conn.commit()
            return True

        return False
    finally:
        conn.close()


def _get_version(conn: sqlite3.Connection) -> int:
    """获取数据库版本"""
    try:
        row = conn.execute("SELECT value FROM metadata WHERE key = 'version'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        # metadata表不存在，创建它
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('version', '0')")
        conn.commit()
        return 0


def _set_version(conn: sqlite3.Connection, version: int):
    """设置数据库版本"""
    conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('version', ?)", (str(version),))


def _get_migrations(from_version: int) -> list:
    """获取需要执行的迁移"""
    migrations = []

    if from_version < 1:
        migrations.append(_migrate_v1)

    return migrations


def _migrate_v1(conn: sqlite3.Connection):
    """迁移到版本1：添加索引"""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_work ON episodes(work_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_danmaku_episode ON danmaku(episode_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_work ON comments(work_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_aid ON comments(aid)")


def discover_work_database(output_dir: Path, work_key: str) -> Path:
    """
    查找作品的数据库文件

    Args:
        output_dir: 输出目录
        work_key: 作品标识

    Returns:
        数据库文件路径
    """
    # 尝试在输出目录中查找
    for db_path in output_dir.rglob("data.db"):
        return db_path

    # 创建新的数据库路径
    safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in work_key)[:50]
    return output_dir / safe_key / "data.db"


def _safe_name(value: str) -> str:
    """生成安全的文件名（与exporter.py保持一致）"""
    import re
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value)).strip(" .")
    return value[:120] or "未命名"


def resolve_database_path(db_path: Path = None, output_dir: Path = None, title: str = None) -> Path:
    """
    解析数据库路径

    Args:
        db_path: 指定的数据库路径
        output_dir: 输出目录
        title: 作品标题

    Returns:
        数据库文件路径
    """
    if db_path:
        return db_path

    if output_dir and title:
        # 使用与exporter.py相同的safe_name函数
        safe_title = _safe_name(title)
        # 数据库文件直接放在视频标题文件夹中，与Excel文件同级
        folder = output_dir / safe_title
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "data.db"

    return Path("data.db")
