"""
Centralized Path Definitions
============================
Single source of truth for database and project paths.
All paths are dynamic and can be overridden via environment variables.
"""
import os

# Project root directory (SFA_V5)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data directory - can be overridden for Railway/Docker deployments
# Local: uses default "data/db" inside project
# Railway: set SFA_DATA_DIR=/app/data/db
DATA_DIR = os.getenv("SFA_DATA_DIR", os.path.join(BASE_DIR, "data", "db"))

# Backup directory for volume initialization (not affected by volume mount)
BACKUP_DIR = os.path.join(BASE_DIR, "data", "db_backup")

# Financial database path
DB_PATH = os.path.join(DATA_DIR, "financial_data.db")

# Users/accounts database path
USERS_DB_PATH = os.path.join(DATA_DIR, "users_accounts_data.db")

# Debug/logs directory
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
