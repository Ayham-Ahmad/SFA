"""
Financial Value Formatters
==========================
Unified functions for parsing and formatting financial values.
Consolidates duplicate logic from graph_pipeline.py, graph_builder.py, and sql_tools.py
"""
from typing import Union


def parse_financial_value(value_str: str) -> float:
    """
    Parse formatted financial value strings to float.
    
    Examples:
        "$219.66B" -> 219660000000.0
        "$1.5M" -> 1500000.0
        "1,234.56" -> 1234.56
        "$50K" -> 50000.0
    
    Args:
        value_str: Formatted value string
        
    Returns:
        Float value
    """
    if not value_str or value_str in ['nan', '-', 'None', 'null', '']:
        return 0.0
    
    # Clean the string
    cleaned = str(value_str).replace('$', '').replace(',', '').replace('%', '').strip()
    
    # Handle suffixes
    multiplier = 1
    if cleaned.endswith('T'):
        multiplier = 1e12
        cleaned = cleaned[:-1]
    elif cleaned.endswith('B'):
        multiplier = 1e9
        cleaned = cleaned[:-1]
    elif cleaned.endswith('M'):
        multiplier = 1e6
        cleaned = cleaned[:-1]
    elif cleaned.endswith('K'):
        multiplier = 1e3
        cleaned = cleaned[:-1]
    
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return 0.0


def format_financial_value(val: Union[int, float, str]) -> str:
    """
    Format number to readable financial string with suffix.
    
    Examples:
        1000000000 -> "$1.00B"
        1500000 -> "$1.50M"
        50000 -> "$50.00K"
        1234.56 -> "$1,234.56"
    
    Args:
        val: Numeric value to format
        
    Returns:
        Formatted string like "$1.50B"
    """
    try:
        val = float(val)
        abs_val = abs(val)
        
        if abs_val >= 1e12:
            return f"${val/1e12:.2f}T"
        elif abs_val >= 1e9:
            return f"${val/1e9:.2f}B"
        elif abs_val >= 1e6:
            return f"${val/1e6:.2f}M"
        elif abs_val >= 1e3:
            return f"${val/1e3:.2f}K"
        else:
            return f"${val:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def format_date(ddate: Union[int, str]) -> str:
    """
    Format YYYYMMDD integer to YYYY-MM-DD string.
    
    Examples:
        20240315 -> "2024-03-15"
        
    Args:
        ddate: Date as integer or string (YYYYMMDD format)
        
    Returns:
        Formatted date string
    """
    try:
        ddate_str = str(int(ddate))
        if len(ddate_str) == 8:
            return f"{ddate_str[:4]}-{ddate_str[4:6]}-{ddate_str[6:]}"
        return ddate_str
    except (ValueError, TypeError):
        return str(ddate)


def format_large_number(val: Union[int, float, None], prefix: str = "$") -> str:
    """
    Format numbers with B/M/K suffixes for display.
    
    Args:
        val: Numeric value
        prefix: Currency prefix (default "$")
        
    Returns:
        Formatted string like "$1.5B" or "-" if None
    """
    if val is None:
        return "-"
    
    try:
        abs_val = abs(val)
        
        if abs_val >= 1_000_000_000_000:
            formatted_num = val / 1_000_000_000_000
            suffix = "T"
        elif abs_val >= 1_000_000_000:
            formatted_num = val / 1_000_000_000
            suffix = "B"
        elif abs_val >= 1_000_000:
            formatted_num = val / 1_000_000
            suffix = "M"
        elif abs_val >= 1_000:
            formatted_num = val / 1_000
            suffix = "K"
        else:
            return f"{prefix}{val:,.2f}"
        
        s = f"{formatted_num:.1f}"
        if s.endswith(".0"):
            s = s[:-2]
        return f"{prefix}{s}{suffix}"
    except (ValueError, TypeError):
        return "-"


def format_percentage(val: Union[int, float, None], decimal_places: int = 1) -> str:
    """
    Format decimal values as percentages.
    
    Handles both decimal form (0.35 -> 35%) and already-percentage form (35 -> 35%).
    
    Args:
        val: Numeric value (decimal like 0.35 or already percentage like 35)
        decimal_places: Number of decimal places to show
        
    Returns:
        Formatted string like "35.0%" or "-" if None
    """
    if val is None:
        return "-"
    
    try:
        val = float(val)
        
        # If value is between -1 and 1, it's likely a decimal (0.35 = 35%)
        # Convert to percentage
        if -1 <= val <= 1 and val != 0:
            val = val * 100
        
        return f"{val:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "-"


def is_percentage_column(column_name: str) -> bool:
    """
    Check if a column name indicates percentage data.
    
    Args:
        column_name: Name of the column
        
    Returns:
        True if column appears to contain percentage data
    """
    col_lower = column_name.lower()
    percentage_indicators = [
        'margin', 'pct', 'percent', 'percentage', 'rate', 'ratio',
        'growth', 'return', 'volatility', 'yield'
    ]
    
    for indicator in percentage_indicators:
        if indicator in col_lower:
            return True
    
    return False
