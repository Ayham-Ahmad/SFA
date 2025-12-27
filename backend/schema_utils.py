"""
Schema Utility Module - DEPRECATED
==================================
This module is kept for backward compatibility with tests.
Schema information is now dynamically obtained from user's connected database
via MultiTenantDBManager.
"""


def get_table_columns(table_name: str, db_path: str = None):
    """DEPRECATED: Use MultiTenantDBManager.get_schema_for_user() instead."""
    return []


def get_all_tables(db_path: str = None):
    """DEPRECATED: Use MultiTenantDBManager.get_schema_for_user() instead."""
    return []


def get_table_columns_with_types(table_name: str, db_path: str = None):
    """DEPRECATED: Use MultiTenantDBManager.get_schema_for_user() instead."""
    return []


def get_complete_schema_dict(db_path: str = None):
    """DEPRECATED: Use MultiTenantDBManager.get_schema_for_user() instead."""
    return {"tables": [], "schema": {}}


def get_columns_for_llm(db_path: str = None):
    """DEPRECATED: Use sql_tools.get_table_schemas(user) instead."""
    return ""


def get_schema_for_prompt():
    """DEPRECATED: Use sql_tools.get_table_schemas(user) instead."""
    return ""


def get_full_schema_context():
    """DEPRECATED: Use sql_tools.get_table_schemas(user) instead."""
    return ""


def get_data_year_range():
    """DEPRECATED: Year range depends on user's connected database."""
    return (2000, 2025)


def get_latest_year():
    """DEPRECATED: Latest year depends on user's connected database."""
    return 2025


def get_dynamic_examples(latest_year: int = None):
    """DEPRECATED."""
    if latest_year is None:
        latest_year = 2025
    return {
        'latest': latest_year,
        'previous': latest_year - 1,
        'three_years_ago': latest_year - 3,
    }
