"""
Markdown Table Parser
=====================
Unified parser for extracting data from markdown tables.
Consolidates logic from graph_pipeline.py and graph_builder.py
"""
import re
from typing import Optional, Dict, List, Any


def parse_markdown_table(text: str) -> Optional[Dict[str, List[Any]]]:
    """
    Parse markdown table from text into structured data.
    
    Args:
        text: Text containing a markdown table
        
    Returns:
        Dictionary with column names as keys and lists of values,
        or None if no valid table found.
        
    Example:
        Input: "| yr | qtr | revenue |\\n|:--|:--|--:|\\n| 2024 | 1 | $50B |"
        Output: {"yr": ["2024"], "qtr": ["1"], "revenue": ["$50B"]}
    """
    lines = text.strip().split('\n')
    table_lines = []
    in_table = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('|') and '|' in line[1:]:
            in_table = True
            table_lines.append(line)
        elif in_table and not line.startswith('|'):
            # End of table
            if len(table_lines) >= 2:
                break
            else:
                table_lines = []
                in_table = False
    
    if len(table_lines) < 2:
        return None
    
    # Parse header
    header_line = table_lines[0]
    headers = [h.strip().lower() for h in header_line.split('|') if h.strip()]
    
    # Skip separator line (|:---|:---|)
    data_start = 1
    if len(table_lines) > 1 and re.match(r'^\|[\s\-:]+\|', table_lines[1]):
        data_start = 2
    
    # Parse data rows
    result = {h: [] for h in headers}
    
    for line in table_lines[data_start:]:
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) == len(headers):
            for i, header in enumerate(headers):
                result[header].append(cells[i])
    
    return result if any(result.values()) else None


def extract_labels_and_values(
    table_data: Dict[str, List[Any]],
    preferred_label_cols: List[str] = None,
    preferred_value_cols: List[str] = None
) -> Dict[str, List]:
    """
    Extract labels and values from parsed table data.
    
    Intelligently combines year+quarter for time-series labels.
    
    Args:
        table_data: Dictionary from parse_markdown_table
        preferred_label_cols: Priority list for label columns
        preferred_value_cols: Priority list for value columns
        
    Returns:
        {"labels": [...], "values": [...], "columns": [...]}
    """
    if not table_data:
        return {"labels": [], "values": [], "columns": []}
    
    columns = list(table_data.keys())
    
    # Default preference orders
    if preferred_label_cols is None:
        preferred_label_cols = ['company_name', 'name', 'company', 'date', 'period']
    
    if preferred_value_cols is None:
        preferred_value_cols = ['actual_value', 'revenue', 'value', 'val', 'close', 
                                'total', 'net_income', 'amount']
    
    # Find year and quarter columns for smart label creation
    year_col = None
    qtr_col = None
    date_col = None
    
    year_patterns = ['yr', 'year', 'fiscal_year', 'fy']
    qtr_patterns = ['qtr', 'quarter', 'fiscal_quarter', 'q']
    date_patterns = ['date', 'month', 'mo', 'period', 'time']
    
    for col in columns:
        col_lower = col.lower()
        # Check for year column
        if year_col is None:
            for pattern in year_patterns:
                if pattern == col_lower or col_lower.startswith(pattern):
                    year_col = col
                    break
        # Check for quarter column
        if qtr_col is None:
            for pattern in qtr_patterns:
                if pattern == col_lower or col_lower.startswith(pattern):
                    qtr_col = col
                    break
        # Check for date column
        if date_col is None:
            for pattern in date_patterns:
                if pattern in col_lower:
                    date_col = col
                    break
    
    # Extract labels with smart combining
    labels = []
    rows_count = len(list(table_data.values())[0]) if table_data else 0
    
    for i in range(rows_count):
        # Priority 1: Combine year + quarter if both exist
        if year_col and qtr_col:
            year_val = table_data[year_col][i]
            qtr_val = table_data[qtr_col][i]
            labels.append(f"{year_val} Q{qtr_val}")
        # Priority 2: Use date column if available
        elif date_col:
            labels.append(table_data[date_col][i])
        # Priority 3: Use quarter column alone
        elif qtr_col:
            labels.append(f"Q{table_data[qtr_col][i]}")
        # Priority 4: Try preferred label columns
        else:
            label_added = False
            for pref_col in preferred_label_cols:
                if pref_col in table_data:
                    labels.append(table_data[pref_col][i])
                    label_added = True
                    break
            if not label_added:
                # Fallback: use first column
                labels.append(table_data[columns[0]][i])
    
    # Find best value column
    value_col = None
    
    # First try preferred columns
    for pref in preferred_value_cols:
        for col in columns:
            if pref in col.lower():
                value_col = col
                break
        if value_col:
            break
    
    # Fallback: find last numeric column that's not a date/identifier
    if not value_col:
        skip_cols = ['yr', 'qtr', 'mo', 'wk', 'date', 'quarter', 'month', 
                     'status', 'metric', 'year']
        for col in reversed(columns):
            col_lower = col.lower()
            if col_lower not in skip_cols and 'pct' not in col_lower and 'percent' not in col_lower:
                value_col = col
                break
    
    # If still no value column, use the last column
    if not value_col:
        value_col = columns[-1]
    
    values = table_data.get(value_col, [])
    
    return {
        "labels": labels,
        "values": values,
        "columns": columns,
        "value_column": value_col
    }
