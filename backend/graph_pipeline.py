"""
Graph Pipeline - Clean Rebuild
Single source of truth for graph generation.

Flow:
1. Get data via SQL (uses existing worker)
2. LLM picks chart type (simple classification)
3. Return raw data + chart type (frontend builds chart from templates)

NO LLM-generated chart code. All chart rendering is done in frontend with hardcoded templates.
"""
import os
import sqlite3
import json
from typing import Dict, Any, Optional, List
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "db", "financial_data.db")

# LLM client for chart type selection only
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
FAST_MODEL = "llama-3.1-8b-instant"


def select_chart_type(question: str, data_description: str) -> str:
    """
    Use LLM to select the best chart type based on the question.
    Returns one of: 'bar', 'line', 'pie', 'scatter'
    """
    prompt = f"""Select the best chart type for this financial question and data.

Question: {question}
Data: {data_description}

CHART SELECTION RULES:
- bar: Compare categories (companies, quarters, items)
- line: Show trends over time (yearly, quarterly, monthly)
- pie: Show parts of a whole (expense breakdown, percentages)
- scatter: Show correlation between two metrics

RESPOND WITH ONLY ONE WORD: bar, line, pie, or scatter"""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=FAST_MODEL,
            temperature=0,
            max_tokens=10
        )
        chart_type = response.choices[0].message.content.strip().lower()
        
        if chart_type in ['bar', 'line', 'pie', 'scatter']:
            print(f"[GraphPipeline] LLM selected: {chart_type}")
            return chart_type
        
        print(f"[GraphPipeline] Invalid type '{chart_type}', defaulting to bar")
        return 'bar'
    except Exception as e:
        print(f"[GraphPipeline] Chart type selection failed: {e}")
        return 'bar'


def execute_graph_query(question: str) -> Optional[Dict[str, Any]]:
    """
    Execute SQL query to get data for graph.
    Uses run_chain_of_tables which generates SQL and returns formatted results.
    """
    from backend.llm import run_chain_of_tables
    
    print(f"\n[GraphPipeline] ========== GRAPH QUERY START ==========")
    print(f"[GraphPipeline] Question: {question}")
    
    # run_chain_of_tables generates SQL internally and returns formatted results
    result = run_chain_of_tables(question)
    
    if not result:
        print("[GraphPipeline] ERROR: No result from chain_of_tables")
        return None
    
    print(f"[GraphPipeline] Result length: {len(result)} chars")
    print(f"[GraphPipeline] Full result:\n{result[:1000]}")
    
    # Check for error or no data signals
    if "Error" in result or "NO_DATA_FOUND" in result:
        print(f"[GraphPipeline] ERROR: Query returned error or no data signal")
        return None
    
    # Check if result contains a markdown table
    if '|' not in result:
        print(f"[GraphPipeline] ERROR: No markdown table found in result")
        return None
    
    print(f"[GraphPipeline] ========== GRAPH QUERY SUCCESS ==========\n")
    return {"result": result}


def parse_table_result(result_text: str) -> Optional[Dict[str, List]]:
    """
    Parse markdown table result into lists of labels and values.
    Returns: {labels: [], values: [], columns: []}
    """
    print(f"[GraphPipeline] Parsing result text (first 500 chars):\n{result_text[:500]}")
    
    lines = result_text.strip().split('\n')
    table_lines = [l for l in lines if l.strip().startswith('|')]
    
    if len(table_lines) < 2:
        print("[GraphPipeline] No valid table found")
        return None
    
    # Parse header
    header = table_lines[0]
    columns = [c.strip().lower() for c in header.split('|') if c.strip()]
    print(f"[GraphPipeline] Columns found: {columns}")
    
    # Skip separator line
    data_start = 1
    if len(table_lines) > 1 and '---' in table_lines[1]:
        data_start = 2
    
    # Parse rows
    rows = []
    for line in table_lines[data_start:]:
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) == len(columns):
            rows.append(cells)
    
    if not rows:
        print("[GraphPipeline] No data rows found")
        return None
    
    print(f"[GraphPipeline] Found {len(rows)} data rows")
    
    # Smart label detection: prefer qtr, then date, then first column
    label_col_idx = 0
    for i, col in enumerate(columns):
        if 'qtr' in col or 'quarter' in col:
            label_col_idx = i
            break
        elif 'date' in col or 'month' in col or 'mo' == col:
            label_col_idx = i
    
    # If first column is 'yr' and second is 'qtr', combine them
    combine_yr_qtr = False
    if len(columns) >= 2 and 'yr' in columns[0] and 'qtr' in columns[1]:
        combine_yr_qtr = True
    
    # Extract labels
    labels = []
    for row in rows:
        if combine_yr_qtr:
            labels.append(f"Q{row[1]} {row[0]}")  # e.g., "Q1 2024"
        else:
            labels.append(row[label_col_idx])
    
    # Find best value column: prefer actual_value, revenue, etc over variance
    # Priority: actual_value > revenue > value > anything numeric
    preferred_cols = ['actual_value', 'revenue', 'value', 'val', 'close', 'total']
    value_col_idx = len(columns) - 1
    
    # First try to find preferred columns
    for preferred in preferred_cols:
        for i, col in enumerate(columns):
            if preferred in col:
                value_col_idx = i
                break
        else:
            continue
        break
    else:
        # Fallback: find last numeric column that's not a percentage
        for i in range(len(columns) - 1, -1, -1):
            col_name = columns[i]
            if col_name in ['yr', 'qtr', 'mo', 'wk', 'date', 'quarter', 'month', 'status', 'metric']:
                continue
            if 'pct' in col_name or 'percent' in col_name:
                continue  # Skip percentage columns
            value_col_idx = i
            break
    
    print(f"[GraphPipeline] Using label col {label_col_idx} ({columns[label_col_idx]}), value col {value_col_idx} ({columns[value_col_idx]})")
    
    # Extract values
    values = []
    for row in rows:
        val = parse_numeric(row[value_col_idx])
        values.append(val)
    
    print(f"[GraphPipeline] Extracted labels: {labels[:5]}...")
    print(f"[GraphPipeline] Extracted values: {values[:5]}...")
    
    return {
        "labels": labels,
        "values": values,
        "columns": columns,
        "raw_rows": rows
    }


def parse_numeric(value_str: str) -> float:
    """Parse formatted value like '$219.66B' or '1,234.56' to float."""
    if not value_str or value_str in ['nan', '-', 'None', 'null']:
        return 0.0
    
    cleaned = value_str.replace('$', '').replace(',', '').replace('%', '').strip()
    
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


def generate_title(question: str) -> str:
    """Generate chart title from question."""
    q = question.lower()
    
    if 'revenue' in q:
        return 'Revenue Analysis'
    elif 'income' in q or 'profit' in q:
        return 'Net Income Analysis'
    elif 'expense' in q or 'cost' in q:
        return 'Expense Analysis'
    elif 'stock' in q or 'price' in q:
        return 'Stock Price Analysis'
    elif 'margin' in q:
        return 'Margin Analysis'
    elif 'growth' in q:
        return 'Growth Analysis'
    else:
        return 'Financial Analysis'


def run_graph_pipeline(question: str, query_id: str = None) -> Dict[str, Any]:
    """
    Main graph pipeline function.
    
    Returns:
    {
        "success": bool,
        "chart_type": "bar" | "line" | "pie" | "scatter",
        "labels": [...],
        "values": [...],
        "title": "...",
        "message": "..."
    }
    """
    print(f"\n[GraphPipeline] Starting for: {question}")
    
    # Step 1: Get data via SQL
    query_result = execute_graph_query(question)
    
    if not query_result:
        return {
            "success": False,
            "message": "No data available for this query.",
            "chart_type": None,
            "labels": [],
            "values": [],
            "title": ""
        }
    
    # Step 2: Parse the result
    parsed = parse_table_result(query_result["result"])
    
    if not parsed or not parsed["values"]:
        return {
            "success": False,
            "message": "Could not extract graphable data from the results.",
            "chart_type": None,
            "labels": [],
            "values": [],
            "title": ""
        }
    
    # Step 3: Select chart type
    data_desc = f"Labels: {parsed['labels'][:5]}, Values: {parsed['values'][:5]}"
    chart_type = select_chart_type(question, data_desc)
    
    # Step 4: Generate title
    title = generate_title(question)
    
    print(f"[GraphPipeline] Success - {chart_type} chart with {len(parsed['labels'])} points")
    
    return {
        "success": True,
        "chart_type": chart_type,
        "labels": parsed["labels"],
        "values": parsed["values"],
        "title": title,
        "message": "Graph ready! Click a slot to place it."
    }


# Test function
if __name__ == "__main__":
    result = run_graph_pipeline("Revenue for 2024")
    print(json.dumps(result, indent=2))
