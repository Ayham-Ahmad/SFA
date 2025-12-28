"""
Dashboard Configuration Routes
================================
Dashboard settings save/load and data retrieval endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db_session import get_db
from api.models import User
from api.auth_utils import get_current_active_user
from api.config_models import DashboardConfig
from backend.services.config_service import ConfigService
from backend.services.tenant_manager import MultiTenantDBManager
from backend.services.ticker_service import ticker_service

router = APIRouter(prefix="/api", tags=["Configuration"])


@router.get("/config/dashboard")
async def get_dashboard_config(current_user: User = Depends(get_current_active_user)):
    """Get saved dashboard configuration for the current user."""
    config = ConfigService.load_dashboard_config(current_user)
    
    if config:
        return {"success": True, "config": config.model_dump()}
    else:
        return {"success": True, "config": None, "message": "No configuration saved yet"}


@router.post("/config/dashboard")
async def save_dashboard_config(
    config: DashboardConfig,
    current_user: User = Depends(get_current_active_user)
):
    """Save dashboard configuration for the current user."""
    result = ConfigService.save_dashboard_config(current_user, config)
    return result


@router.post("/config/expression/evaluate")
async def evaluate_expression(
    request: dict,
    current_user: User = Depends(get_current_active_user)
):
    """
    Evaluate a mathematical expression using latest data from user's database.
    Used for traffic light live updates.
    """
    expression = request.get("expression", "")
    table_name = request.get("table_name")
    
    result = ConfigService.evaluate_expression(current_user, expression, table_name)
    return result


@router.get("/dashboard/data")
async def get_dashboard_data(current_user: User = Depends(get_current_active_user)):
    """
    Get dashboard data based on user's saved configuration.
    Fetches latest row from database and evaluates configured expression.
    """
    # Load user's config
    config = ConfigService.load_dashboard_config(current_user)
    
    if not config:
        # Fall back to legacy data
        return {"data": ticker_service.get_batch()}
    
    if not current_user.db_is_connected:
        return {"error": "No database connected"}
    
    try:
        # Get the primary table from config (extract from any metric column)
        table_name = None
        for col in [config.traffic_light.metric1_column, 
                    config.traffic_light.metric2_column, 
                    config.traffic_light.metric3_column]:
            if col and '.' in col:
                table_name = col.split('.')[0]
                break
        
        if not table_name:
            # Try to get first non-config table
            schema_result = MultiTenantDBManager.get_schema_for_user(current_user)
            if schema_result.get("success"):
                schema = schema_result.get("schema", {})
                tables = list(schema.get("schema", {}).keys()) if isinstance(schema, dict) else []
                tables = [t for t in tables if not t.startswith("_sfa_")]
                if tables:
                    table_name = tables[0]
        
        if not table_name:
            return {"error": "Could not determine data table"}
        
        # Fetch latest row
        query = f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 1"
        result = MultiTenantDBManager.execute_query_for_user(current_user, query)
        
        if not result.get("success"):
            return {"error": result.get("error", "Query failed")}
        
        # Build latest_row dict from columns and rows
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        latest_row = {}
        if rows and columns:
            for i, col in enumerate(columns):
                latest_row[col] = rows[0][i] if i < len(rows[0]) else None
        
        # Evaluate expression if configured
        expression_value = None
        if config.traffic_light.expression:
            expr_result = ConfigService.evaluate_expression(
                current_user, 
                config.traffic_light.expression, 
                table_name
            )
            if expr_result.get("success"):
                expression_value = expr_result.get("value")
        
        # Fetch graph data if configured
        graph1_data = None
        graph2_data = None
        
        if config.graph1.x_column and config.graph1.y_column:
            graph1_data = _fetch_graph_data(current_user, config.graph1, table_name)
        
        if config.graph2.x_column and config.graph2.y_column:
            graph2_data = _fetch_graph_data(current_user, config.graph2, table_name)
        
        return {
            "latest_row": latest_row,
            "expression_value": expression_value,
            "graph1_data": graph1_data,
            "graph2_data": graph2_data
        }
        
    except Exception as e:
        return {"error": str(e)}


def _fetch_graph_data(user, graph_config, default_table: str):
    """Fetch data for a graph based on config."""
    x_col = graph_config.x_column
    y_col = graph_config.y_column
    
    # Extract table and column names
    x_table = x_col.split('.')[0] if '.' in x_col else default_table
    x_name = x_col.split('.')[1] if '.' in x_col else x_col
    y_table = y_col.split('.')[0] if '.' in y_col else default_table
    y_name = y_col.split('.')[1] if '.' in y_col else y_col
    
    # Use the first table for query
    table = x_table
    
    query = f"SELECT {x_name}, {y_name} FROM {table} ORDER BY {x_name}"
    result = MultiTenantDBManager.execute_query_for_user(user, query)
    
    if not result.get("success") or not result.get("rows"):
        return None
    
    rows = result["rows"]
    return {
        "x": [row[0] for row in rows],
        "y": [row[1] for row in rows]
    }
