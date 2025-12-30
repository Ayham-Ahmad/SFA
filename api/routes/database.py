"""
Database Connection Routes
===========================
Multi-tenant database connection management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.db_session import get_db
from api.models import User
from api.auth_utils import get_current_active_user
from backend.services.tenant_manager import MultiTenantDBManager

router = APIRouter(prefix="/api/database", tags=["Database"])


class DatabaseConnectRequest(BaseModel):
    db_type: str
    config: dict


class DatabaseQueryRequest(BaseModel):
    query: str


@router.get("/types")
async def get_database_types():
    """
    Get list of supported database types with their connection fields.
    Used by frontend to dynamically generate connection forms.
    """
    return {
        "types": MultiTenantDBManager.get_supported_types()
    }


@router.post("/test")
async def test_database_connection(
    request: DatabaseConnectRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Test a database connection without saving it."""
    result = MultiTenantDBManager.test_connection(request.db_type, request.config)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/connect")
async def connect_database(
    request: DatabaseConnectRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Connect user to an external database.
    Saves encrypted connection configuration to user record.
    """
    result = MultiTenantDBManager.connect_database(
        current_user, 
        request.db_type, 
        request.config,
        db
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/status")
async def get_database_status(current_user: User = Depends(get_current_active_user)):
    """Get current database connection status for the user."""
    return MultiTenantDBManager.get_connection_status(current_user)


@router.get("/schema")
async def get_database_schema(current_user: User = Depends(get_current_active_user)):
    """
    Get schema of connected database.
    Returns tables dict with column info for frontend dropdowns.
    """
    result = MultiTenantDBManager.get_schema_for_user(current_user)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    tables_dict = result.get("tables", {})
    
    return {
        "success": True,
        "tables": tables_dict,
        "schema_for_llm": result.get("schema_for_llm", "")
    }


@router.post("/query")
async def execute_database_query(
    request: DatabaseQueryRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Execute a SQL query on user's connected database.
    Complete isolation - users can only query their own database.
    """
    result = MultiTenantDBManager.execute_query_for_user(current_user, request.query)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Query failed"))
    
    return result


class DisconnectRequest(BaseModel):
    delete_all_data: bool = True


@router.post("/disconnect")
async def disconnect_database(
    request: DisconnectRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect user from their external database.
    Removes encrypted configuration AND optionally deletes all user data
    (chat history, dashboard config, saved graphs).
    """
    # Disconnect from tenant manager
    result = MultiTenantDBManager.disconnect_database(current_user, db)
    
    if result.get("success") and (request is None or request.delete_all_data):
        # Clear dashboard configuration for fresh start (keep chat history)
        try:
            # Clear dashboard configuration only
            current_user.dashboard_config_encrypted = None
            
            db.commit()
            result["data_deleted"] = True
            result["message"] = "Database disconnected and dashboard config cleared"
        except Exception as e:
            print(f"Error clearing dashboard config: {e}")
            result["data_deleted"] = False
    
    return result

