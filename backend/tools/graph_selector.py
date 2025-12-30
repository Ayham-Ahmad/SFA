"""
Graph Template Selector Tool
============================
Allows the agent to visualize data using pre-defined frontend templates.
Returns a JSON structure compatible with manager_analytics.js buildChartFromTemplate().
"""
import json
from langchain_core.tools import Tool
from typing import List, Dict, Any

# Available templates in manager_analytics.js
# - revenue_trend (Area chart)
# - stock_price (Line chart)
# - expenses (Pie chart)
# - net_income (Bar chart with pos/neg colors)
# - bar (Generic bar)
# - line (Generic line)
TEMPLATE_OPTIONS = ["revenue_trend", "stock_price", "expenses", "net_income", "bar", "line"]

def select_graph_template(input_str: str) -> str:
    """
    Parses input to generate a graph specification.
    Expected Input Dictionary (JSON string):
    {
        "template": "bar",
        "title": "My Graph Title",
        "labels": ["A", "B", "C"],
        "values": [10, 20, 30],
        "y_label": "USD",
        "is_percentage": false
    }
    """
    try:
        # 1. Parse Input
        # Clean potential markdown wrapping
        clean_input = input_str.strip().replace("```json", "").replace("```", "")
        params = json.loads(clean_input)
        
        # 2. Validation
        template = params.get("template", "bar")
        if template not in TEMPLATE_OPTIONS:
            return f"Error: Invalid template '{template}'. usage: {TEMPLATE_OPTIONS}"
            
        labels = params.get("labels", [])
        values = params.get("values", [])
        
        if not labels or not values:
            return "Error: 'labels' and 'values' arrays are required."
            
        if len(labels) != len(values):
            return "Error: labels and values must have the same length."

        # 3. Construct Output
        # This structure matches what the frontend expects in `chart_data`
        graph_spec = {
            "chart_type": template, # mapped to template in JS
            "title": params.get("title", "Data Graph"),
            "labels": labels,
            "values": values,
            "y_label": params.get("y_label", "Value"),
            "is_percentage": params.get("is_percentage", False)
        }
        
        # Return as JSON string to be included in Final Answer
        return json.dumps(graph_spec)

    except json.JSONDecodeError:
        return "Error: Input must be valid JSON string."
    except Exception as e:
        return f"Graph Tool Error: {e}"

def get_graph_tool() -> Tool:
    return Tool(
        name="generate_graph",
        func=select_graph_template,
        description=f"""
        Use this tool to visualize data. Input must be a JSON string with keys: 'template', 'title', 'labels' (x-axis list), 'values' (y-axis list).
        Templates: {TEMPLATE_OPTIONS}.
        Example: {{"template": "bar", "title": "Revenue by User", "labels": ["User A", "User B"], "values": [100, 200]}}
        """
    )
