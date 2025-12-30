"""
SQLite Manager
==============
Handles SQLite database connections and schema extraction.
"""

import os
import sqlite3
from typing import Dict, List, Any, Optional


class SQLiteManager:
    """
    Manager for SQLite database files.
    Handles connection, schema extraction, and query execution.
    Uses new connection for each operation for thread safety.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SQLite manager.
        
        Args:
            config: Configuration dict with 'path' key
        """
        self.db_path = config.get("path", "")
        self.is_connected = False
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a new thread-safe connection."""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def connect(self) -> bool:
        """
        Verify database file exists and is accessible.
        
        Returns:
            True if database is valid
        """
        try:
            if not os.path.exists(self.db_path):
                return False
            
            # Test connection
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            self.is_connected = True
            return True
        except Exception as e:
            print(f"SQLite connect error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Mark as disconnected."""
        self.is_connected = False
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection.
        
        Returns:
            Dict with success, message, tables
        """
        if not os.path.exists(self.db_path):
            return {"success": False, "message": f"Database file not found: {self.db_path}"}
        
        if not self.db_path.lower().endswith('.db'):
            return {"success": False, "message": "File must have .db extension"}
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return {
                "success": True,
                "message": f"Connected successfully. Found {len(tables)} tables.",
                "tables": tables
            }
        except Exception as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}
    
    def get_tables(self) -> List[str]:
        """
        Get all table names from the database.
        
        Returns:
            List of table names
        """
        if not self.is_connected:
            self.connect()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_sfa_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Exception as e:
            print(f"get_tables error: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dict with columns, types, count, primary_key, foreign_keys
        """
        if not self.is_connected:
            self.connect()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get column info
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = []
            primary_key = None
            for row in cursor.fetchall():
                col_info = {
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "nullable": not row[3],
                    "default": row[4],
                    "is_primary_key": bool(row[5])
                }
                columns.append(col_info)
                if row[5]:
                    primary_key = row[1]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
            row_count = cursor.fetchone()[0]
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
            foreign_keys = []
            for row in cursor.fetchall():
                foreign_keys.append({
                    "column": row[3],
                    "references_table": row[2],
                    "references_column": row[4]
                })
            
            # Get indexes
            cursor.execute(f"PRAGMA index_list('{table_name}')")
            indexes = [row[1] for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns),
                "row_count": row_count,
                "primary_key": primary_key,
                "foreign_keys": foreign_keys,
                "indexes": indexes
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_full_schema(self) -> Dict[str, Any]:
        """
        Get complete schema for all tables.
        
        Returns:
            Dict with tables list and detailed schema for each
        """
        tables = self.get_tables()
        schema = {}
        
        for table in tables:
            schema[table] = self.get_table_schema(table)
        
        return {
            "success": True,
            "tables": tables,
            "schema": schema,
            "table_count": len(tables)
        }
    
    def get_schema_for_llm(self) -> str:
        """
        Get formatted schema string for LLM consumption.
        
        Returns:
            Formatted schema string
        """
        schema = self.get_full_schema()
        parts = []
        
        for table_name, table_info in schema.get("schema", {}).items():
            cols = table_info.get("columns", [])
            col_list = ", ".join([f"{c['name']} ({c['type']})" for c in cols])
            # Wrap table name in backticks for SQL safety (handles numeric/special names)
            parts.append(f"TABLE: `{table_name}`\nCOLUMNS: {col_list}\nROWS: {table_info.get('row_count', 0)}")
        
        return "\n\n".join(parts)
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query (thread-safe).
        
        Args:
            query: SQL query string
            
        Returns:
            Dict with success, columns, rows, row_count or error
        """
        if not self.is_connected:
            if not self.connect():
                return {"success": False, "error": "Failed to connect"}
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                conn.close()
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                conn.commit()
                row_count = cursor.rowcount
                conn.close()
                return {
                    "success": True,
                    "message": "Query executed",
                    "row_count": row_count
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_required_fields() -> List[Dict[str, str]]:
        """Get required connection fields."""
        return [
            {
                "name": "path",
                "label": "Database File Path",
                "type": "text",
                "required": True,
                "placeholder": "C:\\data\\financial.db"
            }
        ]
