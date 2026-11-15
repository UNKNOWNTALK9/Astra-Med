import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import BACKUP_DIR
from database.models import TABLES


def create_backup(db, dest_dir=BACKUP_DIR):
    """Consistent online backup using SQLite's backup API."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"astra_med_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    out = sqlite3.connect(str(dest))
    try:
        db.conn.backup(out)
    finally:
        out.close()
    db.log("INFO", "backup", f"Backup created: {dest.name}")
    return dest


def list_backups(dest_dir=BACKUP_DIR):
    return sorted(Path(dest_dir).glob("astra_med_backup_*.db"), reverse=True)


def validate_backup(path):
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
        return all(t in names for t in TABLES)
    except sqlite3.Error:
        return False


def restore_backup(db, path):
    """Validate, make a safety copy, close the live DB and replace it. Caller must restart the app."""
    path = Path(path)
    if not validate_backup(path):
        raise ValueError("Selected file is not a valid ASTRA-MED database backup.")
    safety = create_backup(db)
    live = db.path
    db.close()
    for ext in ("-wal", "-shm"):
        Path(str(live) + ext).unlink(missing_ok=True)
    shutil.copy2(path, live)
    return safety
