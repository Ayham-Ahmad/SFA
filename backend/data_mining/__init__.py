"""
Data Collection Manager Package
================================
Handles different data source types (SQLite, CSV, etc.)
Each source type has its own dedicated manager.
"""

from .manager import DataCollectionManager
from .sqlite_manager import SQLiteManager
from .csv_manager import CSVManager

__all__ = ['DataCollectionManager', 'SQLiteManager', 'CSVManager']
