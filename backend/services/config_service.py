"""
config_service.py - Service for managing user dashboard configurations.

Stores configuration in the USERS database (not the financial database).
"""

import json
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
from api.config_models import DashboardConfig, TrafficLightConfig, GraphConfig
from backend.services.tenant_manager import MultiTenantDBManager
from backend.core.logger import log_system_error, log_system_info
from backend.utils.paths import USERS_DB_PATH


class ConfigService:
    """Service for managing user dashboard configurations stored in users DB."""
    
    CONFIG_TABLE_NAME = "_sfa_user_config"
    DASHBOARD_CONFIG_KEY = "dashboard_config"
    
    @staticmethod
    def _get_connection():
        """Get a connection to the users database."""
        return sqlite3.connect(USERS_DB_PATH)
    
    @staticmethod
    def ensure_config_table() -> bool:
        """
        Creates _sfa_user_config table in users DB if it doesn't exist.
        
        Returns:
            True if table exists or was created successfully, False otherwise.
        """
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {ConfigService.CONFIG_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            config_key TEXT NOT NULL,
            config_value TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, config_key)
        )
        """
        
        try:
            conn = ConfigService._get_connection()
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log_system_error(f"Failed to create config table: {e}")
            return False
    
    @staticmethod
    def save_dashboard_config(user, config: DashboardConfig) -> Dict[str, Any]:
        """
        Saves dashboard configuration to the users database.
        
        Args:
            user: The current user object
            config: DashboardConfig object to save
            
        Returns:
            Dict with success status and message
        """
        # Ensure config table exists
        if not ConfigService.ensure_config_table():
            return {"success": False, "message": "Failed to create config table"}
        
        # Serialize config to JSON
        config_json = config.model_dump_json()
        current_time = datetime.utcnow().isoformat()
        
        try:
            conn = ConfigService._get_connection()
            cursor = conn.cursor()
            
            # Upsert the configuration
            cursor.execute(f"""
                INSERT OR REPLACE INTO {ConfigService.CONFIG_TABLE_NAME} 
                (user_id, config_key, config_value, updated_at)
                VALUES (?, ?, ?, ?)
            """, (user.id, ConfigService.DASHBOARD_CONFIG_KEY, config_json, current_time))
            
            conn.commit()
            conn.close()
            
            log_system_info(f"Dashboard config saved for user {user.id}")
            return {"success": True, "message": "Configuration saved successfully"}
            
        except Exception as e:
            log_system_error(f"Failed to save dashboard config: {e}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def load_dashboard_config(user) -> Optional[DashboardConfig]:
        """
        Loads dashboard configuration from the users database.
        
        Args:
            user: The current user object
            
        Returns:
            DashboardConfig object if found, None otherwise
        """
        try:
            conn = ConfigService._get_connection()
            cursor = conn.cursor()
            
            # Check if table exists first
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{ConfigService.CONFIG_TABLE_NAME}'
            """)
            
            if not cursor.fetchone():
                conn.close()
                return None  # Table doesn't exist yet
            
            # Fetch config
            cursor.execute(f"""
                SELECT config_value FROM {ConfigService.CONFIG_TABLE_NAME}
                WHERE user_id = ? AND config_key = ?
            """, (user.id, ConfigService.DASHBOARD_CONFIG_KEY))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                config_json = row[0]
                config_dict = json.loads(config_json)
                return DashboardConfig(**config_dict)
            
            return None
            
        except Exception as e:
            log_system_error(f"Failed to load dashboard config: {e}")
            return None
    
    @staticmethod
    def get_table_columns(user, table_name: str) -> List[Dict[str, str]]:
        """
        Gets column information for a specific table in user's FINANCIAL database.
        
        Args:
            user: The current user object
            table_name: Name of the table to inspect
            
        Returns:
            List of dicts with 'name' and 'type' keys
        """
        if not user.db_is_connected:
            return []
        
        # SQLite PRAGMA for table info - uses user's financial DB
        pragma_sql = f"PRAGMA table_info({table_name})"
        
        try:
            result = MultiTenantDBManager.execute_query_for_user(user, pragma_sql)
            
            if result.get("success") and result.get("rows"):
                columns = []
                for row in result["rows"]:
                    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
                    columns.append({
                        "name": row[1],
                        "type": row[2] or "TEXT"
                    })
                return columns
            
            return []
            
        except Exception as e:
            log_system_error(f"Failed to get table columns: {e}")
            return []
    
    @staticmethod
    def evaluate_expression(user, expression: str, table_name: str = None) -> Dict[str, Any]:
        """
        Evaluates a mathematical expression using the latest row from a table
        in the user's FINANCIAL database.
        
        Args:
            user: The current user object
            expression: Mathematical expression using column names
            table_name: Optional table name (auto-detected from expression if not provided)
            
        Returns:
            Dict with success, value, and any error message
        """
        if not user.db_is_connected:
            return {"success": False, "error": "No database connected"}
        
        if not expression or not expression.strip():
            return {"success": False, "error": "Empty expression"}
        
        # Basic security: only allow alphanumeric, spaces, and math operators
        import re
        if not re.match(r'^[\w\s\+\-\*\/\(\)\.]+$', expression):
            return {"success": False, "error": "Invalid characters in expression"}
        
        try:
            # Build a SELECT query with the expression
            # We need to find the table to query - extract from column references
            
            # Try to detect table from expression (look for table.column patterns)
            table_match = re.search(r'(\w+)\.(\w+)', expression)
            if table_match:
                table_name = table_match.group(1)
            
            if not table_name:
                # Default to first available table
                schema_result = MultiTenantDBManager.get_schema_for_user(user)
                if schema_result.get("success") and schema_result.get("tables"):
                    tables = list(schema_result["tables"].keys())
                    # Filter out our config table (though it's in users DB now)
                    tables = [t for t in tables if not t.startswith("_sfa_")]
                    if tables:
                        table_name = tables[0]
            
            if not table_name:
                return {"success": False, "error": "Could not determine table"}
            
            # Clean expression for SQL (remove table prefixes for simpler query)
            clean_expr = re.sub(r'(\w+)\.(\w+)', r'\2', expression)
            
            # Query latest row and evaluate expression
            eval_sql = f"SELECT ({clean_expr}) as result FROM {table_name} ORDER BY rowid DESC LIMIT 1"
            
            result = MultiTenantDBManager.execute_query_for_user(user, eval_sql)
            
            if result.get("success") and result.get("rows"):
                value = result["rows"][0][0]
                return {"success": True, "value": value}
            else:
                return {"success": False, "error": result.get("error", "Evaluation failed")}
                
        except Exception as e:
            log_system_error(f"Expression evaluation error: {e}")
            return {"success": False, "error": str(e)}
