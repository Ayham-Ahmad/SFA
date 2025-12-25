"""
config_models.py - Pydantic models for dashboard configuration.
"""

from pydantic import BaseModel
from typing import Optional


class TrafficLightConfig(BaseModel):
    """Configuration for the traffic light widget on the dashboard."""
    metric1_column: Optional[str] = None  
    metric1_format: Optional[str] = "text" # text, number, currency, percentage, date
    metric2_column: Optional[str] = None  
    metric2_format: Optional[str] = "text"
    metric3_column: Optional[str] = None  
    metric3_format: Optional[str] = "text"
    expression: Optional[str] = None      
    green_threshold: float = 0            
    red_threshold: float = 0              


class GraphConfig(BaseModel):
    """
    Configuration for a default graph.
    """
    graph_type: str = "line"              
    x_column: Optional[str] = None        
    x_format: Optional[str] = "text"
    y_column: Optional[str] = None        
    y_format: Optional[str] = "text"
    title: Optional[str] = None           


class DashboardConfig(BaseModel):
    """Complete dashboard configuration including traffic light and graphs."""
    traffic_light: TrafficLightConfig = TrafficLightConfig()
    graph1: GraphConfig = GraphConfig()   
    graph2: GraphConfig = GraphConfig()   
    ticker_title_column: Optional[str] = None 
    ticker_title_format: Optional[str] = "text"
    refresh_interval: int = 10            

