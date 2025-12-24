"""
Centralized Path Definitions
============================
Single source of truth for database and project paths.
"""
import os

# Project root directory (SFA_V5)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database path
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")

# Debug/logs directory
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
