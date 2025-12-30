"""
Analytics Routes
==================
Dashboard metrics and analytics data endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException

from api.models import User
from api.auth_utils import get_current_active_user
from backend.core.logger import log_system_info, log_system_error
from backend.services.config_service import ConfigService

from backend.services.tenant_manager import MultiTenantDBManager
from backend.utils.formatters import format_value

router = APIRouter(prefix="/api/dashboard", tags=["Analytics"])


# --- Helper Functions ---

def _empty_graph(title: str, chart_type: str) -> dict:
    """Returns an empty graph structure."""
    return {"dates": [], "values": [], "title": title, "chart_type": chart_type}


def _parse_column(column: str) -> tuple:
    """
    Parses 'table.column' format into (table, column_name).
    Returns (None, column) if no table prefix.
    """
    if '.' in column:
        parts = column.split('.', 1)
        return parts[0], parts[1]
    return None, column


# --- Routes ---

@router.get("/metrics")
async def dashboard_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Aggregates high-level metrics for the default graphs on Analytics page.
    Uses saved config from settings if available. No hardcoded fallbacks.
    """
    try:
        config = ConfigService.load_dashboard_config(current_user)
        
        # Default: empty data until user configures graphs
        graph1_data = _empty_graph(None, None)
        graph2_data = _empty_graph(None, None)
        
        # Only populate if user has configured the graph (type + columns required)
        if config:
            if config.graph1.graph_type and config.graph1.x_column and config.graph1.y_column:
                graph1_data = _fetch_configured_graph_data(
                    current_user, 
                    config.graph1.x_column, 
                    config.graph1.y_column,
                    config.graph1.title,
                    config.graph1.graph_type,
                    config.graph1.x_format,
                    config.graph1.y_format,
                    config.graph1
                )
            
            if config.graph2.graph_type and config.graph2.x_column and config.graph2.y_column:
                graph2_data = _fetch_configured_graph_data(
                    current_user,
                    config.graph2.x_column,
                    config.graph2.y_column,
                    config.graph2.title,
                    config.graph2.graph_type,
                    config.graph2.x_format,
                    config.graph2.y_format,
                    config.graph2
                )
        
        return {"graph1": graph1_data, "graph2": graph2_data}
    except Exception as e:
        import traceback
        log_system_error(f"Dashboard Metrics Error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def _fetch_configured_graph_data(
    user, 
    x_column: str, 
    y_column: str, 
    title: str, 
    chart_type: str,
    x_format: str,
    y_format: str,
    graph_config: object = None
) -> dict:
    """
    Fetch graph data using user-configured columns.
    
    Args:
        user: Active user
        x_column: Column name for X-axis
        y_column: Column name for Y-axis
        title: Graph title
        chart_type: Graph type (line/bar/scatter)
        x_format: Format (text/date/etc)
        y_format: Format (number/currency/etc)
        graph_config: Optional GraphConfig object containing range and secondary column settings
        
    Returns:
        Graph data dictionary
    """
    
    # Check connection
    if not user.db_is_connected:
        return _empty_graph(title, chart_type)
    
    # Parse column references
    x_table, x_name = _parse_column(x_column)
    _, y_name = _parse_column(y_column)
    
    # Check for secondary X column
    x_secondary_name = None
    if graph_config and hasattr(graph_config, 'x_secondary_column') and graph_config.x_secondary_column:
        _, x_secondary_name = _parse_column(graph_config.x_secondary_column)
    
    if not x_table:
        return _empty_graph(title, chart_type)
    
    # Build query - include secondary column if present
    if x_secondary_name:
        query = f'SELECT "{x_name}", "{x_secondary_name}", "{y_name}" FROM "{x_table}" ORDER BY "{x_name}", "{x_secondary_name}"'
    else:
        query = f'SELECT "{x_name}", "{y_name}" FROM "{x_table}" ORDER BY "{x_name}"'
    
    result = MultiTenantDBManager.execute_query_for_user(user, query)
    
    if not result.get("success") or not result.get("rows"):
        return _empty_graph(title, chart_type)
    
    rows = result["rows"]
    
    # --- Data Filtering Logic ---
    if graph_config and hasattr(graph_config, 'data_range_mode') and graph_config.data_range_mode == "last_n":
        limit = graph_config.data_range_limit or 12
        if len(rows) > limit:
            rows = rows[-limit:]
    
    # Build labels - combine if secondary column exists
    if x_secondary_name:
        # Row format: (x_primary, x_secondary, y_value)
        dates = [f"{format_value(row[0], x_format)} {format_value(row[1], 'text')}" for row in rows]
        values = [row[2] for row in rows]
    else:
        # Row format: (x_primary, y_value)
        dates = [format_value(row[0], x_format) for row in rows]
        values = [row[1] for row in rows]
            
    return {
        "dates": dates,
        "values": values,
        "title": title,
        "chart_type": chart_type,
        "x_label": x_name.replace('_', ' ').title(),
        "y_label": y_name.replace('_', ' ').title(),
        "x_format": x_format,
        "y_format": y_format
    }
