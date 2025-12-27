from pydantic import BaseModel
from typing import Optional

# 1. Settings for the "Traffic Light" (Status Indicator)
class TrafficLightConfig(BaseModel):
    # These are the names of the columns in your database/dataframe
    metric1_column: Optional[str] = None
    metric1_format: Optional[str] = "text"  # e.g., "currency", "percentage"
    
    metric2_column: Optional[str] = None
    metric2_format: Optional[str] = "text"
    
    metric3_column: Optional[str] = None
    metric3_format: Optional[str] = "text"
    
    # The math formula to decide the status (e.g., "metric1 > 50")
    expression: Optional[str] = None
    
    # The numbers that trigger the light changes
    green_threshold: float = 0
    red_threshold: float = 0

# 2. Settings for a single Graph/Chart
class GraphConfig(BaseModel):
    graph_type: Optional[str] = None  # User must configure: "line", "bar", "scatter"
    
    # Which data column goes on the horizontal (X) axis?
    x_column: Optional[str] = None
    x_secondary_column: Optional[str] = None  # Optional: combine with x_column (e.g., "2025 Q1")
    x_format: Optional[str] = "text"
    
    # Which data column goes on the vertical (Y) axis?
    y_column: Optional[str] = None
    y_format: Optional[str] = "text"
    
    # Data Range Settings
    data_range_mode: Optional[str] = "all"  # "all" or "last_n"
    data_range_limit: Optional[int] = 12    # Default limit if mode is "last_n"

    title: Optional[str] = None

# 3. Master Settings for the whole Dashboard
class DashboardConfig(BaseModel):
    # This nests the settings from above inside the main config
    traffic_light: TrafficLightConfig = TrafficLightConfig()
    
    # We create two default graphs
    graph1: GraphConfig = GraphConfig()
    graph2: GraphConfig = GraphConfig()
    
    # Settings for the scrolling ticker title
    ticker_title_column: Optional[str] = None
    ticker_title_secondary_column: Optional[str] = None  # Optional: combine (e.g., "2025 Q4")
    ticker_title_format: Optional[str] = "text"
    
    # How often the data updates (in seconds)
    refresh_interval: int = 10