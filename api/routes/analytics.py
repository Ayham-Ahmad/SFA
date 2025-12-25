"""
Analytics Routes
==================
Dashboard metrics and analytics data endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException

from api.models import User
from api.auth import get_current_active_user
from backend.config_service import ConfigService
from backend.tenant_manager import MultiTenantDBManager
from backend.sfa_logger import log_system_error

router = APIRouter(prefix="/api/dashboard", tags=["Analytics"])


@router.get("/metrics")
async def dashboard_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Aggregates high-level metrics for the default graphs on Analytics page.
    Uses saved config from settings if available. No hardcoded fallbacks.
    """
    try:
        # Try to load user's saved config for graph columns
        config = ConfigService.load_dashboard_config(current_user)
        
        trend = {"dates": [], "values": [], "title": "Configure Graph 1", "chart_type": "line"}
        income_trend = {"dates": [], "values": [], "title": "Configure Graph 2", "chart_type": "bar"}
        
        if config:
            if config.graph1.x_column and config.graph1.y_column:
                trend = _fetch_configured_graph_data(
                    current_user, 
                    config.graph1.x_column, 
                    config.graph1.y_column,
                    config.graph1.title or "Graph 1",
                    config.graph1.graph_type or "line",
                    x_format=config.graph1.x_format,
                    y_format=config.graph1.y_format
                )
            
            if config.graph2.x_column and config.graph2.y_column:
                income_trend = _fetch_configured_graph_data(
                    current_user,
                    config.graph2.x_column,
                    config.graph2.y_column,
                    config.graph2.title or "Graph 2",
                    config.graph2.graph_type or "bar",
                    x_format=config.graph2.x_format,
                    y_format=config.graph2.y_format
                )
        
        return {"trend": trend, "income_trend": income_trend}
    except Exception as e:
        import traceback
        log_system_error(f"Dashboard Metrics Error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def _fetch_configured_graph_data(
    user, 
    x_column: str, 
    y_column: str, 
    title: str, 
    chart_type: str = "line",
    x_format: str = "text",
    y_format: str = "text"
):
    """Fetch graph data using user-configured columns."""
    if not user.db_is_connected:
        return {"dates": [], "values": [], "title": title, "chart_type": chart_type}
    
    # Extract table and column names
    x_table = x_column.split('.')[0] if '.' in x_column else None
    x_name = x_column.split('.')[1] if '.' in x_column else x_column
    y_name = y_column.split('.')[1] if '.' in y_column else y_column
    
    if not x_table:
        return {"dates": [], "values": [], "title": title, "chart_type": chart_type}
    
    query = f'SELECT "{x_name}", "{y_name}" FROM "{x_table}" ORDER BY "{x_name}"'
    result = MultiTenantDBManager.execute_query_for_user(user, query)
    
    if not result.get("success") or not result.get("rows"):
        return {"dates": [], "values": [], "title": title, "chart_type": chart_type}
    
    rows = result["rows"]
    
    # Generate labels
    x_label = x_name.replace('_', ' ').title()
    y_label = y_name.replace('_', ' ').title()
    
    from backend.utils.formatters import format_value
    
    # Format X values into strings (labels)
    dates = [format_value(row[0], x_format) for row in rows]
    # Y values must remain numbers for plotting
    values = [row[1] for row in rows]
    
    return {
        "dates": dates,
        "values": values,
        "title": title,
        "chart_type": chart_type,
        "x_label": x_label,
        "y_label": y_label,
        "x_format": x_format,
        "y_format": y_format
    }
