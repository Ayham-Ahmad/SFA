"""
Graph Pipeline - Clean Rebuild
==============================
Single source of truth for graph generation.

Flow:
1. Get data via SQL (uses existing worker)
2. LLM picks chart type (simple classification)
3. Return raw data + chart type (frontend builds chart from templates)

NO LLM-generated chart code. All chart rendering is done in frontend with hardcoded templates.
"""
import json
from typing import Dict, Any, Optional, List
from backend.utils.llm_client import groq_client, get_model
from backend.utils.formatters import parse_financial_value, is_percentage_column
from backend.utils.table_parser import parse_markdown_table, extract_labels_and_values
from backend.core.logger import log_system_debug, log_system_error

# Fast model for chart type selection
FAST_MODEL = get_model("fast")

def generate_title(question: str) -> str:
    """Helper alias for tests."""
    return get_chart_metadata(question, "")["title"]

def select_chart_type(question: str, data_description: str) -> str:
    """Helper alias for tests."""
    return get_chart_metadata(question, data_description)["chart_type"]

def get_chart_metadata(question: str, data_description: str) -> dict:
    """
    Use LLM to select chart type AND generate appropriate title.
    
    Returns: {"chart_type": "bar|line|pie|scatter", "title": "..."}
    """
    prompt = f"""Analyze this financial data request and return chart metadata.

Question: {question}
Data Sample: {data_description}

CHART TYPE RULES:
- bar: Compare categories (companies, quarters, expense items)
- line: Show trends over time (yearly, quarterly, monthly data)
- pie: Show parts of a whole (expense breakdown, portfolio allocation)
- scatter: Show correlation between two numeric metrics

TITLE RULES:
- Be specific: Include the metric name (Revenue, Net Income, Gross Income, etc.)
- IMPORTANT: If values are in billions/millions (e.g., 2500000000), use "Revenue" or "Income" NOT "Margin"
- Only use "Margin" in the title if values are percentages (0.35 or 35%)
- Include time period if mentioned in the question
- Keep it concise (max 6 words)
- Do NOT use generic titles like "Financial Analysis"

RESPOND WITH ONLY THIS JSON FORMAT (no markdown, no explanation):
{{"chart_type": "bar", "title": "Your Specific Title Here"}}
"""

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=FAST_MODEL,
            temperature=0,
            max_tokens=100
        )
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            metadata = json.loads(json_match.group())
            chart_type = metadata.get("chart_type", "bar").lower()
            title = metadata.get("title", "Financial Analysis")
            
            # Validate chart_type
            if chart_type not in ['bar', 'line', 'pie', 'scatter']:
                chart_type = 'bar'
            
            log_system_debug(f"[GraphPipeline] LLM metadata: type={chart_type}, title={title}")
            return {"chart_type": chart_type, "title": title}
        
        log_system_debug(f"[GraphPipeline] Failed to parse JSON, using defaults")
        return {"chart_type": "bar", "title": "Financial Analysis"}
        
    except Exception as e:
        log_system_error(f"[GraphPipeline] Metadata generation failed: {e}")
        return {"chart_type": "bar", "title": "Financial Analysis"}


def execute_graph_query(question: str, user=None) -> Optional[Dict[str, Any]]:
    """
    Execute SQL query to get data for graph using LangChain agent's reasoning.
    
    The agent uses its intelligence to determine the right SQL query,
    then returns raw markdown table data for graph parsing.
    
    Args:
        question: User's question
        user: Optional User model instance for tenant-specific queries
    """
    from backend.agents.langchain_agent import LangChainAgent
    
    log_system_debug(f"========== GRAPH QUERY START ==========")
    log_system_debug(f"[GraphPipeline] Question: {question}")
    
    # Use LangChain agent with graph_mode=True to get raw table data
    agent = LangChainAgent(user=user)
    result = agent.run(question, graph_mode=True)
    
    if not result:
        log_system_error("[GraphPipeline] ERROR: No result from LangChain agent")
        return None
    
    log_system_debug(f"[GraphPipeline] Result length: {len(result)} chars")
    
    # Check for error or no data signals
    if "error" in result.lower() or "NO_DATA_FOUND" in result:
        log_system_error(f"[GraphPipeline] ERROR: Query returned error or no data signal")
        return None
    
    # Check if result contains a markdown table
    if '|' not in result:
        log_system_error(f"[GraphPipeline] ERROR: No markdown table found in result")
        return None
    
    log_system_debug(f"========== GRAPH QUERY SUCCESS ==========")
    return {"result": result}


def parse_table_result(result_text: str) -> Optional[Dict[str, List]]:
    """
    Parse markdown table result into lists of labels and values.
    
    Returns: {labels: [], values: [], columns: []}
    """
    log_system_debug(f"[GraphPipeline] Parsing result text (first 500 chars):\n{result_text[:500]}")
    
    lines = result_text.strip().split('\n')
    table_lines = [l for l in lines if l.strip().startswith('|')]
    
    if len(table_lines) < 2:
        log_system_error("[GraphPipeline] No valid table found")
        return None
    
    # Parse header
    header = table_lines[0]
    columns = [c.strip().lower() for c in header.split('|') if c.strip()]
    log_system_debug(f"[GraphPipeline] Columns found: {columns}")
    
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
        log_system_error("[GraphPipeline] No data rows found")
        return None
    
    log_system_debug(f"[GraphPipeline] Found {len(rows)} data rows")
    
    # ==========================================
    # SMART LABEL DETECTION
    # ==========================================
    
    # Find year and quarter columns
    year_col_idx = None
    qtr_col_idx = None
    date_col_idx = None
    
    year_patterns = ['yr', 'year', 'fiscal_year', 'fy']
    qtr_patterns = ['qtr', 'quarter', 'fiscal_quarter', 'q']
    date_patterns = ['date', 'month', 'mo', 'period', 'time']
    
    for i, col in enumerate(columns):
        col_lower = col.lower()
        if year_col_idx is None:
            for pattern in year_patterns:
                if pattern == col_lower or col_lower.startswith(pattern):
                    year_col_idx = i
                    break
        if qtr_col_idx is None:
            for pattern in qtr_patterns:
                if pattern == col_lower or col_lower.startswith(pattern):
                    qtr_col_idx = i
                    break
        if date_col_idx is None:
            for pattern in date_patterns:
                if pattern in col_lower:
                    date_col_idx = i
                    break
    
    log_system_debug(f"[GraphPipeline] Column detection: year_col={year_col_idx}, qtr_col={qtr_col_idx}, date_col={date_col_idx}")
    
    # Extract labels with smart combining
    labels = []
    for row in rows:
        if year_col_idx is not None and qtr_col_idx is not None:
            year_val = row[year_col_idx]
            qtr_val = row[qtr_col_idx]
            labels.append(f"{year_val} Q{qtr_val}")
        elif date_col_idx is not None:
            labels.append(row[date_col_idx])
        elif qtr_col_idx is not None:
            labels.append(f"Q{row[qtr_col_idx]}")
        else:
            labels.append(row[0])
    
    # Find best value column - now includes percentage columns
    preferred_cols = ['actual_value', 'revenue', 'value', 'val', 'close', 'total', 'margin', 'pct']
    value_col_idx = len(columns) - 1
    is_pct = False
    
    for preferred in preferred_cols:
        for i, col in enumerate(columns):
            if preferred in col:
                value_col_idx = i
                break
        else:
            continue
        break
    else:
        for i in range(len(columns) - 1, -1, -1):
            col_name = columns[i]
            if col_name in ['yr', 'qtr', 'mo', 'wk', 'date', 'quarter', 'month', 'status', 'metric']:
                continue
            value_col_idx = i
            break
    
    # Check if value column is a percentage type
    value_col_name = columns[value_col_idx]
    is_pct = is_percentage_column(value_col_name)
    
    log_system_debug(f"[GraphPipeline] Using value col {value_col_idx} ({value_col_name}), is_percentage={is_pct}")
    
    # Extract values
    values = []
    for row in rows:
        raw_val = row[value_col_idx]
        if is_pct:
            # For percentage columns, parse as float and convert if needed
            try:
                val = float(raw_val.replace('%', '').replace('$', '').strip())
                # If already in decimal form (0.35), convert to percentage (35)
                if -1 <= val <= 1 and val != 0:
                    val = val * 100
            except (ValueError, AttributeError):
                val = 0.0
        else:
            val = parse_financial_value(raw_val)
        values.append(val)
    
    log_system_debug(f"[GraphPipeline] Extracted labels: {labels[:5]}...")
    log_system_debug(f"[GraphPipeline] Extracted values: {values[:5]}...")
    
    # Sort chronologically if labels look like dates or time periods
    # This ensures graphs show oldest -> newest (left to right)
    if labels and len(labels) > 1:
        try:
            sample = str(labels[0])
            
            # Detect various time series formats
            is_time_series = (
                '-' in sample or              # YYYY-MM-DD format
                '/' in sample or              # MM/DD/YYYY format
                sample.startswith('Q') or     # Q1, Q2, etc
                'Q' in sample or              # 2025 Q1, 2024 Q4, etc
                (len(sample) == 4 and sample.isdigit())  # Year only
            )
            
            if is_time_series:
                # Custom sort key for "YYYY QX" format
                def sort_key(item):
                    label = str(item[0])
                    # Handle "2025 Q1" format
                    if ' Q' in label:
                        parts = label.split(' Q')
                        try:
                            year = int(parts[0])
                            quarter = int(parts[1]) if len(parts) > 1 else 0
                            return (year, quarter)
                        except (ValueError, IndexError):
                            return (0, 0)
                    # Handle "Q1", "Q2" format
                    elif label.startswith('Q') and len(label) == 2:
                        try:
                            return (0, int(label[1]))
                        except ValueError:
                            return (0, 0)
                    # Default string sort
                    return (0, label)
                
                # Sort chronologically (oldest to newest)
                sorted_pairs = sorted(zip(labels, values), key=sort_key)
                labels, values = zip(*sorted_pairs)
                labels = list(labels)
                values = list(values)
                log_system_debug(f"[GraphPipeline] Sorted chronologically: {labels[:3]}... -> {labels[-3:]}")
        except Exception as e:
            log_system_debug(f"[GraphPipeline] Sort skipped: {e}")
    
    return {
        "labels": labels,
        "values": values,
        "columns": columns,
        "raw_rows": rows,
        "is_percentage": is_pct,
        "value_column": value_col_name
    }


def run_graph_pipeline(question: str, query_id: str = None, user=None) -> Dict[str, Any]:
    """
    Main graph pipeline function.
    
    Args:
        question: User's question
        query_id: Optional query ID for progress tracking
        user: Optional User model instance for tenant-specific queries
    
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
    log_system_debug(f"[GraphPipeline] Starting for: {question}")
    
    # Step 1: Get data via SQL (user-specific)
    query_result = execute_graph_query(question, user=user)
    
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
    
    # Step 3: Get chart type and title from LLM
    data_desc = f"Labels: {parsed['labels'][:5]}, Values: {parsed['values'][:5]}"
    metadata = get_chart_metadata(question, data_desc)
    chart_type = metadata["chart_type"]
    title = metadata["title"]
    
    # Step 4: Check for complex data
    unique_labels = set(parsed["labels"])
    is_complex = len(unique_labels) < len(parsed["labels"]) * 0.8
    
    if is_complex:
        message = "Graph ready! Tip: For clearer charts, try adding a specific metric, date range, or quarter to your query."
    else:
        message = "Graph ready! Click a slot to place it."
    
    # Step 5: Determine if percentage data and set axis title
    is_percentage = parsed.get("is_percentage", False)
    y_axis_title = "%" if is_percentage else "USD"
    
    # For percentage time-series, prefer line chart
    if is_percentage and chart_type == "bar":
        chart_type = "line"  # Line better shows percentage trends
    
    log_system_debug(f"[GraphPipeline] Success - {chart_type} chart with {len(parsed['labels'])} points, is_percentage={is_percentage}")
    
    return {
        "success": True,
        "chart_type": chart_type,
        "labels": parsed["labels"],
        "values": parsed["values"],
        "title": title,
        "message": message,
        "is_percentage": is_percentage,
        "y_axis_title": y_axis_title
    }
