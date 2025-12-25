"""
Multi-Tenant Database Manager (Revised)
========================================
Manages external database connections using the new data_collection_manager.
Connection info stored in User model for complete isolation.
"""
import json
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
import os

from backend.utils.paths import BASE_DIR
from backend.data_collection_manager import DataCollectionManager, SQLiteManager, CSVManager
from backend.sfa_logger import log_system_info, log_system_error


# Key storage for encryption
KEY_FILE = os.path.join(BASE_DIR, "data", ".db_encryption_key")


def get_encryption_key() -> bytes:
    """Get or create encryption key."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key


def encrypt_config(config: Dict) -> str:
    """Encrypt database configuration."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(json.dumps(config).encode()).decode()


def decrypt_config(encrypted: str) -> Dict:
    """Decrypt database configuration."""
    key = get_encryption_key()
    f = Fernet(key)
    return json.loads(f.decrypt(encrypted.encode()).decode())


class MultiTenantDBManager:
    """
    Manages database connections for multiple users.
    Each user has their own isolated database connection.
    """
    
    # Cache of active managers by user_id
    _managers: Dict[int, Any] = {}
    
    @staticmethod
    def get_supported_types() -> list:
        """Get list of supported database types."""
        return [
            {
                "type": "sqlite",
                "label": "SQLite",
                "fields": SQLiteManager.get_required_fields()
            },
            {
                "type": "csv",
                "label": "CSV",
                "fields": CSVManager.get_required_fields()
            }
        ]
    
    @staticmethod
    def test_connection(db_type: str, config: Dict) -> Dict:
        """
        Test a database connection without saving.
        
        Args:
            db_type: Type of database (sqlite, csv, etc.)
            config: Connection configuration
            
        Returns:
            Result dict with success, message, tables
        """
        return DataCollectionManager.test_connection(db_type, config)
    
    @staticmethod
    def connect_database(user, db_type: str, config: Dict, db_session) -> Dict:
        """
        Connect user to an external database and save configuration.
        
        Args:
            user: User model instance
            db_type: Type of database
            config: Connection configuration
            db_session: SQLAlchemy session
            
        Returns:
            Result dict
        """
        # First test the connection
        test_result = MultiTenantDBManager.test_connection(db_type, config)
        if not test_result["success"]:
            return test_result
        
        # Save encrypted config to user
        from api.models import DatabaseType
        
        user.db_type = DatabaseType(db_type)
        user.db_connection_encrypted = encrypt_config(config)
        user.db_is_connected = True
        
        db_session.commit()
        
        return {
            "success": True,
            "message": f"Successfully connected to {db_type} data source",
            "tables": test_result.get("tables", [])
        }
    
    @staticmethod
    def disconnect_database(user, db_session) -> Dict:
        """
        Disconnect user from their external database.
        
        Args:
            user: User model instance
            db_session: SQLAlchemy session
            
        Returns:
            Result dict
        """
        from api.models import DatabaseType
        
        # Close cached manager
        if user.id in MultiTenantDBManager._managers:
            MultiTenantDBManager._managers[user.id].disconnect()
            del MultiTenantDBManager._managers[user.id]
        
        user.db_type = DatabaseType.NONE
        user.db_connection_encrypted = None
        user.db_is_connected = False
        
        db_session.commit()
        
        return {"success": True, "message": "Database disconnected successfully"}
    
    @staticmethod
    def get_manager_for_user(user) -> Optional[Any]:
        """
        Get data manager for a user.
        
        Args:
            user: User model instance
            
        Returns:
            Manager instance or None
        """
        if not user.db_is_connected or not user.db_connection_encrypted:
            return None
        
        # Check cache
        if user.id in MultiTenantDBManager._managers:
            return MultiTenantDBManager._managers[user.id]
        
        # Create new manager
        config = decrypt_config(user.db_connection_encrypted)
        manager_class = DataCollectionManager.get_manager(user.db_type.value)
        
        if not manager_class:
            return None
        
        manager = manager_class(config)
        manager.connect()
        
        # Cache it
        MultiTenantDBManager._managers[user.id] = manager
        
        return manager
    
    @staticmethod
    def get_schema_for_user(user) -> Dict:
        """
        Get database schema for a user.
        
        Args:
            user: User model instance
            
        Returns:
            Schema dict
        """
        manager = MultiTenantDBManager.get_manager_for_user(user)
        if not manager:
            return {"success": False, "message": "No database connected"}
        
        full_schema = manager.get_full_schema()
        return {
            "success": True,
            "tables": full_schema.get("schema", {}),
            "schema_for_llm": manager.get_schema_for_llm()
        }
    
    @staticmethod
    def execute_query_for_user(user, query: str) -> Dict:
        """
        Execute query on user's database.
        
        Args:
            user: User model instance
            query: SQL query
            
        Returns:
            Query result dict
        """
        manager = MultiTenantDBManager.get_manager_for_user(user)
        if not manager:
            return {"success": False, "error": "No database connected"}
        
        return manager.execute_query(query)
    
    @staticmethod
    def get_connection_status(user) -> Dict:
        """
        Get connection status for a user.
        
        Args:
            user: User model instance
            
        Returns:
            Status dict
        """
        if not user.db_is_connected:
            return {
                "connected": False,
                "db_type": None,
                "db_path": None,
                "message": "No database connected"
            }
        
        # Get the path from encrypted config
        db_path = None
        if user.db_connection_encrypted:
            try:
                config = decrypt_config(user.db_connection_encrypted)
                db_path = config.get("path", "")
                log_system_info(f"[TenantManager] Decrypted config for user {user.id}: path={db_path}")
            except Exception as e:
                log_system_error(f"[TenantManager] Failed to decrypt config for user {user.id}: {e}")
        else:
            log_system_info(f"[TenantManager] No encrypted config for user {user.id}")
        
        db_type_value = user.db_type.value if user.db_type else "unknown"
        
        return {
            "connected": True,
            "db_type": db_type_value,
            "type": db_type_value,  # Alias for frontend
            "db_path": db_path,
            "path": db_path,  # Alias for frontend
            "config": {"path": db_path},  # Legacy format for frontend
            "message": f"Connected to {db_type_value}: {db_path}"
        }


# Global instance
db_manager = MultiTenantDBManager()
