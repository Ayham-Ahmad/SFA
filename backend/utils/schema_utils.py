"""
Schema Utils
============
Helpers for formatting database schemas for LLM consumption.
"""
from typing import Dict, Any
from backend.tenant_manager import MultiTenantDBManager

def get_schema_summary_for_llm(user) -> str:
    """
    Get a concise textual summary of the user's database schema for the LLM.
    
    Args:
        user: User model instance
        
    Returns:
        String describing the available tables and columns.
        Returns a default message if no database is connected.
    """
    if not user.db_is_connected:
        return "No external database connected. The user has not provided any data."
        
    schema_info = MultiTenantDBManager.get_schema_for_user(user)
    
    if not schema_info.get("success"):
        return f"Error retrieving schema: {schema_info.get('message')}"
        
    # If the manager provides a pre-formatted LLM schema string, use it
    if schema_info.get("schema_for_llm"):
        return schema_info["schema_for_llm"]
        
    # Fallback formatting if needed
    tables = schema_info.get("tables", {})
    summary = []
    
    for table_name, details in tables.items():
        if isinstance(details, dict):
            cols = [col["name"] for col in details.get("columns", [])]
        else:
            cols = [col.name for col in details.columns] if hasattr(details, "columns") else []
            
        summary.append(f"Table: {table_name} (Columns: {', '.join(cols)})")
        
    return "\n".join(summary)
