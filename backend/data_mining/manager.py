"""
Data Collection Manager - Main Router
======================================
Routes requests to the appropriate manager based on data source type.
"""

from typing import Dict, Any, Optional
from .sqlite_manager import SQLiteManager
from .csv_manager import CSVManager


# Registry of available managers
MANAGERS = {
    "sqlite": SQLiteManager,
    "csv": CSVManager,
}


class DataCollectionManager:
    """
    Main manager that routes to the appropriate data source handler.
    """
    
    @staticmethod
    def get_manager(source_type: str):
        """
        Get the appropriate manager class for a data source type.
        
        Args:
            source_type: Type of data source ('sqlite', 'csv', etc.)
            
        Returns:
            Manager class or None if unsupported
        """
        return MANAGERS.get(source_type.lower())
    
    @staticmethod
    def get_supported_types() -> list:
        """Get list of supported data source types."""
        return list(MANAGERS.keys())
    
    @staticmethod
    def test_connection(source_type: str, config: Dict) -> Dict[str, Any]:
        """
        Test a data source connection.
        
        Args:
            source_type: Type of data source
            config: Connection configuration (path, etc.)
            
        Returns:
            Result dict with success, message, tables
        """
        manager_class = DataCollectionManager.get_manager(source_type)
        if not manager_class:
            return {
                "success": False, 
                "message": f"Unsupported data source type: {source_type}"
            }
        
        manager = manager_class(config)
        return manager.test_connection()
    
    @staticmethod
    def connect(source_type: str, config: Dict) -> Optional[Any]:
        """
        Create and connect a manager instance.
        
        Args:
            source_type: Type of data source
            config: Connection configuration
            
        Returns:
            Connected manager instance or None
        """
        manager_class = DataCollectionManager.get_manager(source_type)
        if not manager_class:
            return None
        
        manager = manager_class(config)
        if manager.connect():
            return manager
        return None
    
    @staticmethod
    def get_schema(source_type: str, config: Dict) -> Dict[str, Any]:
        """
        Get full schema from a data source.
        
        Args:
            source_type: Type of data source
            config: Connection configuration
            
        Returns:
            Schema dict with tables, columns, types, counts
        """
        manager_class = DataCollectionManager.get_manager(source_type)
        if not manager_class:
            return {"success": False, "message": "Unsupported type"}
        
        manager = manager_class(config)
        if not manager.connect():
            return {"success": False, "message": "Failed to connect"}
        
        schema = manager.get_full_schema()
        manager.disconnect()
        return schema
