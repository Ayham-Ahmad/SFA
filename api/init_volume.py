"""
Volume Initialization Module
=============================
Copies initial database to volume on first boot if it doesn't exist.
This solves the Railway volume overlay problem where the volume hides git files.
"""
import os
import shutil
from backend.utils.paths import DATA_DIR, BACKUP_DIR

DB_FILE = "users_accounts_data.db"


def init_volume():
    """Copy initial database to volume if it doesn't exist."""
    volume_db = os.path.join(DATA_DIR, DB_FILE)
    backup_db = os.path.join(BACKUP_DIR, DB_FILE)
    
    # Ensure volume directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Copy backup to volume if volume is empty
    if not os.path.exists(volume_db):
        if os.path.exists(backup_db):
            shutil.copy(backup_db, volume_db)
            print(f"[Init] Copied {DB_FILE} from backup to volume")
        else:
            print(f"[Init] No backup database found at {backup_db}")
    else:
        print(f"[Init] Database already exists at {volume_db}")

