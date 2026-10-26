"""在迁移前备份当前配置的 SQLite 数据库，不修改原数据库。"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import sys


def backup_sqlite(source, directory, revision):
    source = Path(source).resolve()
    if not source.exists():
        return None  # 首次部署由 migrate 创建空数据库。
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"before_deploy_{stamp}_{revision[:12]}.sqlite3"
    target.touch(mode=0o600, exist_ok=False)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(target) as backup:
            original.backup(backup)
            if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("迁移前备份完整性检查失败")
    return target


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "xmmcg"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xmmcg.settings")
    from django.conf import settings

    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        raise SystemExit("此部署流程仅适用于 SQLite")
    result = backup_sqlite(
        settings.DATABASES["default"]["NAME"], sys.argv[1], sys.argv[2]
    )
    print(f"迁移前备份：{result}" if result else "首次部署：尚无数据库需要备份")
