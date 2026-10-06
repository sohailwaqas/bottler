"""
utils/backup_utils.py — scheduled/manual SQLite backup + restore, built on
the lightweight `backup` package (backup.arc_pack / backup.arc_unpack wrap
shutil.make_archive / shutil.unpack_archive).

Because `backup.arc_pack` archives a *directory*, each backup first stages
a copy of the live SQLite file into a throwaway staging folder, then
compresses that folder into data/backups/bottler_backup_YYYYMMDD_HHMMSS.zip.
"""
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import backup as backup_lib

import config

BACKUP_DIR = config.DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def run_backup(reason: str = "manual") -> Path | None:
    """Create a timestamped .zip backup of the SQLite database. Returns the path, or None on failure."""
    if not config.DB_PATH.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_base = BACKUP_DIR / f"bottler_backup_{ts}_{reason}"
    with tempfile.TemporaryDirectory() as staging:
        staging_path = Path(staging)
        shutil.copy2(config.DB_PATH, staging_path / "bottler.db")
        ok = backup_lib.arc_pack(str(staging_path), str(archive_base), format="zip")
    return Path(f"{archive_base}.zip") if ok else None


def list_backups() -> list[dict]:
    items = []
    for f in sorted(BACKUP_DIR.glob("*.zip"), reverse=True):
        stat = f.stat()
        items.append({
            "file": f.name,
            "path": str(f),
            "size_kb": round(stat.st_size / 1024, 1),
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return items


def restore_backup(backup_path: str) -> bool:
    """Restore the SQLite DB from a backup zip. A safety copy of the current
    DB is taken first so a bad restore can always be undone manually."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        return False
    # Safety snapshot of current state before overwriting.
    run_backup(reason="pre_restore")
    with tempfile.TemporaryDirectory() as extract_dir:
        ok = backup_lib.arc_unpack(str(backup_path), extract_dir=extract_dir, format="zip")
        if not ok:
            return False
        restored_db = Path(extract_dir) / "bottler.db"
        if not restored_db.exists():
            return False
        shutil.copy2(restored_db, config.DB_PATH)
    return True


def should_run_scheduled_backup() -> bool:
    """True if no backup has been taken in the last 24h (simple daily-schedule check)."""
    backups = list_backups()
    if not backups:
        return True
    latest = datetime.strptime(backups[0]["created"], "%Y-%m-%d %H:%M:%S")
    return datetime.now() - latest > timedelta(days=1)


def maybe_run_scheduled_backup():
    if should_run_scheduled_backup():
        run_backup(reason="scheduled")
