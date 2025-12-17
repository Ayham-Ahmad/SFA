"""
Graph Builder Utility

Builds Plotly.js JSON programmatically from SQL results.
This ensures 100% reliable graph generation without depending on LLM output.
"""
import json
import re
import os
from typing import Optional, Dict, List, Any
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client for chart type detection
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
FAST_MODEL = "llama-3.1-8b-instant"  # Fast model for simple classification


def detect_chart_type(question: str, data_summary: str) -> str:
    """
    Use LLM to select the best chart type based on the Graph Decision Matrix.
    Chart building is still programmatic - LLM only selects the type.
    
    Returns one of: 'bar', 'line', 'pie', 'scatter'
    """
    prompt = f"""Based on this question and data, recommend the BEST chart type using the Graph Decision Matrix.

Question: {question}
Data: {data_summary[:300]}

GRAPH DECISION MATRIX:
- Bar/Column → for comparing categories or displaying time-based data (e.g., revenue by company, costs by department)
- Line/Area → for illustrating time trends by date (e.g., revenue over quarters, stock price over months)
- Pie/Donut → for demonstrating part-to-whole relationships (e.g., expense breakdown, market share percentages)
- Scatter → for analyzing relationships between two numeric measures (e.g., price vs volume correlation)

INTENT ANALYSIS:
- Comparative Analysis → Bar
- Time Trend → Line
- Composition/Breakdown → Pie
- Correlation → Scatter

If no clear match is identified, default to Bar.

RESPOND WITH ONLY ONE WORD: bar, line, pie, or scatter

Answer:"""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=FAST_MODEL,
            temperature=0,
            max_tokens=10
        )
        chart_type = response.choices[0].message.content.strip().lower()
        
        # Validate response
        valid_types = ['bar', 'line', 'pie', 'scatter']
        if chart_type in valid_types:
            print(f"[GraphBuilder] LLM selected chart type: {chart_type}")
            return chart_type
        
        # Default to bar if invalid response
        print(f"[GraphBuilder] Invalid chart type '{chart_type}', defaulting to bar")
        return 'bar'
    except Exception as e:
        print(f"[GraphBuilder] Chart type detection failed: {e}, defaulting to bar")
        return 'bar'


def extract_table_data(context: str) -> Optional[Dict[str, List[Any]]]:
    """
    Extract tabular data from markdown table in context.
    Returns dict with column names as keys and lists of values.
    """
    # Look for markdown table pattern
    # Example: | company_name | value |
    #          |:------------|------:|
    #          | APPLE INC   | $219B |
    
    lines = context.split('\n')
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
    headers = [h.strip() for h in header_line.split('|') if h.strip()]
    
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


def parse_value(value_str: str) -> float:
    """
    Parse formatted value like '$219.66B' to raw number.
    """
    if not value_str or value_str == 'nan' or value_str == '-':
        return 0
    
    # Remove $ and other formatting
    cleaned = value_str.replace('$', '').replace(',', '').strip()
    
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
        return 0


def build_bar_chart(labels: List[str], values: List[float], title: str = "Financial Comparison") -> str:
    """Build a Plotly bar chart JSON."""
    filtered = [(l, v) for l, v in zip(labels, values) if v != 0]
    if not filtered:
        return None
    
    labels, values = zip(*filtered)
    
    chart_data = {
        "data": [
            {
                "x": list(labels),
                "y": list(values),
                "type": "bar",
                "name": "Value",
                "marker": {"color": "#4CAF50"}
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": ""},
            "yaxis": {"title": "USD"}
        }
    }
    return json.dumps(chart_data)


def build_line_chart(labels: List[str], values: List[float], title: str = "Financial Trend") -> str:
    """Build a Plotly line chart JSON."""
    filtered = [(l, v) for l, v in zip(labels, values) if v != 0]
    if not filtered:
        return None
    
    labels, values = zip(*filtered)
    
    chart_data = {
        "data": [
            {
                "x": list(labels),
                "y": list(values),
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Trend",
                "line": {"color": "#2196F3", "width": 2},
                "marker": {"size": 8}
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": ""},
            "yaxis": {"title": "USD"}
        }
    }
    return json.dumps(chart_data)


def build_pie_chart(labels: List[str], values: List[float], title: str = "Distribution") -> str:
    """Build a Plotly pie chart JSON."""
    filtered = [(l, v) for l, v in zip(labels, values) if v != 0]
    if not filtered:
        return None
    
    labels, values = zip(*filtered)
    
    chart_data = {
        "data": [
            {
                "labels": list(labels),
                "values": list(values),
                "type": "pie",
                "hole": 0.3,  # Donut style
                "textinfo": "label+percent"
            }
        ],
        "layout": {
            "title": title
        }
    }
    return json.dumps(chart_data)


def build_scatter_chart(labels: List[str], values: List[float], title: str = "Correlation") -> str:
    """Build a Plotly scatter chart JSON."""
    filtered = [(l, v) for l, v in zip(labels, values) if v != 0]
    if not filtered:
        return None
    
    labels, values = zip(*filtered)
    
    chart_data = {
        "data": [
            {
                "x": list(range(len(labels))),
                "y": list(values),
                "type": "scatter",
                "mode": "markers",
                "name": "Data Points",
                "text": list(labels),
                "marker": {"size": 12, "color": "#FF5722"}
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "Index"},
            "yaxis": {"title": "USD"}
        }
    }
    return json.dumps(chart_data)


def build_chart(chart_type: str, labels: List[str], values: List[float], title: str) -> Optional[str]:
    """Build chart based on type."""
    builders = {
        'bar': build_bar_chart,
        'line': build_line_chart,
        'pie': build_pie_chart,
        'scatter': build_scatter_chart
    }
    builder = builders.get(chart_type, build_bar_chart)
    return builder(labels, values, title)


def build_graph_from_context(context: str, question: str) -> Optional[str]:
    """
    Main function: Extract data from context and build graph JSON.
    Returns the Plotly JSON string or None if no graphable data found.
    """
    table_data = extract_table_data(context)
    
    if not table_data:
        print("[GraphBuilder] No table data found in context")
        return None
    
    print(f"[GraphBuilder] Found table with columns: {list(table_data.keys())}")
    
    # Determine which columns to use for labels and values
    label_col = None
    value_col = None
    cols = list(table_data.keys())
    
    # Priority order for label columns
    label_candidates = ['company_name', 'name', 'company', 'Company', 'Name']
    for col in label_candidates:
        if col in table_data:
            label_col = col
            break
    
    # Priority order for value columns
    value_candidates = ['value', 'Value', 'revenue', 'Revenue', 'net_income', 'Net Income', 
                        'stockholders_equity', 'fiscal_year', 'total']
    for col in value_candidates:
        if col in table_data:
            value_col = col
            break
    
    # If no standard columns found, try first and last
    if not label_col and len(cols) >= 1:
        label_col = cols[0]
    if not value_col and len(cols) >= 2:
        value_col = cols[-1]
    
    # SPECIAL CASE: Single column table (just names, no values)
    # Create a simple bar chart with equal heights to show the list visually
    if len(cols) == 1 or not value_col:
        label_col = cols[0]
        labels = table_data[label_col]
        # Assign equal values (1 each) - just to visualize the list
        values = [1] * len(labels)
        
        print(f"[GraphBuilder] Single-column table detected - creating list visualization")
        
        # Generate title
        title = "Companies Meeting Criteria"
        if "negative" in question.lower() and "income" in question.lower():
            title = "Companies with Negative Net Income"
        elif "revenue" in question.lower():
            title = "Companies by Revenue"
        
        # Use horizontal bar for better label visibility with names
        chart_data = {
            "data": [
                {
                    "y": list(labels),
                    "x": values,
                    "type": "bar",
                    "orientation": "h",
                    "marker": {"color": "#f44336"}
                }
            ],
            "layout": {
                "title": title,
                "xaxis": {"title": "Count", "showticklabels": False},
                "yaxis": {"title": ""},
                "margin": {"l": 200}  # Extra margin for long company names
            }
        }
        chart_json = json.dumps(chart_data)
        print(f"[GraphBuilder] Successfully built horizontal bar chart for {len(labels)} items")
        return chart_json
    
    if not label_col or not value_col:
        print("[GraphBuilder] Could not determine label/value columns")
        return None
    
    labels = table_data[label_col]
    raw_values = table_data[value_col]
    values = [parse_value(str(v)) for v in raw_values]
    
    # Generate title from question
    title = "Financial Data"
    if "revenue" in question.lower():
        title = "Revenue Comparison"
    elif "income" in question.lower() or "profit" in question.lower():
        title = "Net Income Comparison"
    elif "asset" in question.lower():
        title = "Assets Comparison"
    elif "equity" in question.lower():
        title = "Stockholders Equity"
    
    # Ask LLM for chart type
    data_summary = f"Labels: {labels[:5]}, Values: {values[:5]}"
    chart_type = detect_chart_type(question, data_summary)
    
    # Build chart with detected type
    chart_json = build_chart(chart_type, labels, values, title)
    
    if chart_json:
        print(f"[GraphBuilder] Successfully built {chart_type} chart with {len(labels)} data points")
    
    return chart_json


# Test function
if __name__ == "__main__":
    test_context = """
Database Results:
| company_name   |   fiscal_year | value    |
|:---------------|--------------:|:---------|
| APPLE INC      |          2025 | $219.66B |
| MICROSOFT CORP |          2025 | $205.28B |
    """
    
    result = build_graph_from_context(test_context, "apple vs microsoft revenue")
    if result:
        print(f"graph_data||{result}||")
    else:
        print("No graph generated")

