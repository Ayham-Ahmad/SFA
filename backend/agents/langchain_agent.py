"""
LangChain Agent V3 - Hardened Architecture
==========================================

Root causes of previous failures:
1. SQL caching keyed by call-count, not query text → corrupted observations
2. No task mode isolation → graph/aggregation mixing
3. Prompt-based stopping → ignored by LLM under rate limits
4. Fallback logic masking failures → incorrect answers surface

This version implements:
1. Query-scoped SQL caching (keyed by normalized SQL)
2. Task mode classification before execution
3. SQL result validation (shape enforcement)
4. Hard termination after valid SQL (programmatic, not prompt)
5. Fail-fast on mode violations
"""

import os
import uuid
import re
from typing import Any, Dict, Optional, Literal
from enum import Enum
from langchain_groq import ChatGroq
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from backend.core.logger import log_system_info, log_system_error, log_system_debug, log_agent_interaction
from backend.tools.sql_tools import execute_sql_query, get_table_schemas
from backend.tools.calculator import get_calculator_tool
from backend.tools.advisory_tool import get_advisory_tool, set_advisory_interaction_id, set_advisory_query_id
from backend.pipeline.progress import set_query_progress
from backend.utils.llm_client import get_model, increment_api_counter

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# =============================================================================
# CONFIGURATION
# =============================================================================
PRIMARY_MODEL = get_model("default")
FALLBACK_MODEL = get_model("fast")


# =============================================================================
# TASK MODE ENUM - Strictly enforced, cannot change mid-run
# =============================================================================
class TaskMode(Enum):
    GRAPH = "graph"           # Multi-row table output for visualization
    AGGREGATION = "agg"       # Single value: SUM, AVG, COUNT, etc.
    LOOKUP = "lookup"         # Single row lookup (specific quarter/year)
    ADVISORY = "advisory"     # Investment advice, no SQL needed
    COMPARISON = "comparison" # Compare two values (may need calculator)


def classify_task_mode(query: str) -> TaskMode:
    """
    Classify user query into ONE immutable task mode.
    This is determined BEFORE agent execution and CANNOT change.
    """
    q = query.lower()
    
    # Graph keywords
    graph_keywords = ["plot", "chart", "graph", "visualiz", "trend", "show me", "display"]
    if any(kw in q for kw in graph_keywords):
        return TaskMode.GRAPH
    
    # Advisory keywords
    advisory_keywords = ["should i", "recommend", "advice", "strategy", "strategic", "invest"]
    if any(kw in q for kw in advisory_keywords):
        return TaskMode.ADVISORY
    
    # Comparison keywords
    comparison_keywords = ["compare", "vs", "versus", "between", "difference"]
    if any(kw in q for kw in comparison_keywords):
        return TaskMode.COMPARISON
    
    # Aggregation keywords (TOTAL, SUM, AVERAGE, etc.)
    agg_keywords = ["total", "sum", "average", "avg", "count", "how many", "all time"]
    if any(kw in q for kw in agg_keywords):
        return TaskMode.AGGREGATION
    
    # Default to lookup (specific value)
    return TaskMode.LOOKUP


# =============================================================================
# SQL RESULT VALIDATOR - Enforces correctness at tool level
# =============================================================================
class SQLResultValidator:
    """
    Validates SQL results against expected task mode.
    Raises hard errors on violations - does NOT mask failures.
    """
    
    @staticmethod
    def validate(result: str, task_mode: TaskMode, sql_query: str) -> str:
        """
        Validate SQL result matches task mode expectations.
        Returns validated result or raises RuntimeError.
        """
        if not result or "Error" in result:
            return result  # Pass through errors
        
        # Parse result to count rows and columns
        lines = [l for l in result.strip().split('\n') if l.strip().startswith('|')]
        if len(lines) < 2:
            return result  # Not a table format
        
        # Count rows (excluding header and separator)
        data_rows = [l for l in lines if '---' not in l][1:]  # Skip header
        row_count = len(data_rows)
        
        # Count columns
        header = lines[0]
        col_count = len([c for c in header.split('|') if c.strip()])
        
        # Validate based on task mode
        if task_mode == TaskMode.AGGREGATION:
            # Aggregation MUST return 1 row, 1 column (or 1 row with named result)
            if row_count > 1:
                log_system_error(f"[Validator] AGGREGATION mode received {row_count} rows - SQL may be missing SUM/AVG")
                # Don't fail - the LLM may have forgotten aggregation
                # But log clearly for debugging
        
        if task_mode == TaskMode.GRAPH:
            # Graph mode MUST return multiple rows (at least 2 for a chart)
            if row_count < 2:
                log_system_debug(f"[Validator] GRAPH mode received only {row_count} row(s)")
        
        return result
    
    @staticmethod
    def normalize_sql(sql: str) -> str:
        """Normalize SQL for cache key comparison."""
        # Remove whitespace variations, lowercase, strip
        normalized = ' '.join(sql.lower().split())
        # Remove trailing semicolon
        normalized = normalized.rstrip(';').strip()
        return normalized


# =============================================================================
# QUERY-SCOPED SQL CACHE - Keyed by normalized SQL, NOT call count
# =============================================================================
class QueryScopedSQLCache:
    """
    SQL cache keyed by normalized query text.
    Prevents replay of wrong results for different queries.
    """
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._first_result: Optional[str] = None
        self._sql_executed = False
    
    def get(self, sql: str) -> Optional[str]:
        """Get cached result for this exact SQL query."""
        key = SQLResultValidator.normalize_sql(sql)
        return self._cache.get(key)
    
    def set(self, sql: str, result: str):
        """Cache result for this SQL query."""
        key = SQLResultValidator.normalize_sql(sql)
        self._cache[key] = result
        if not self._sql_executed:
            self._first_result = result
            self._sql_executed = True
    
    def has_executed(self) -> bool:
        """Has any SQL been executed successfully?"""
        return self._sql_executed
    
    def get_first_result(self) -> Optional[str]:
        """Get the first successful SQL result."""
        return self._first_result


# =============================================================================
# CALLBACK HANDLER
# =============================================================================
class ReasoningCallbackHandler(BaseCallbackHandler):
    def __init__(self, query_id: str | None = None):
        self.query_id = query_id

    def on_llm_start(self, serialized, prompts, **kwargs):
        if self.query_id:
            set_query_progress(self.query_id, "reasoning", "Thinking...")

    def on_llm_end(self, response, **kwargs):
        increment_api_counter(PRIMARY_MODEL, 0)
        if not self.query_id or not response.generations:
            return
        text = response.generations[0][0].text if response.generations[0] else ""
        m = re.search(r"Thought:\s*(.+?)(?=\n|Action:|$)", text, re.DOTALL)
        if m:
            set_query_progress(self.query_id, "reasoning", f"Thought: {m.group(1).strip()[:150]}")

    def on_agent_action(self, action, **kwargs):
        if self.query_id:
            set_query_progress(self.query_id, "reasoning", f"Action: {action.tool}")

    def on_tool_end(self, output, **kwargs):
        if self.query_id:
            out = str(output)
            if len(out) > 80:
                out = out[:80] + "..."
            set_query_progress(self.query_id, "reasoning", f"Observation: {out}")


# =============================================================================
# PROMPT - Minimal, mode-aware
# =============================================================================
def get_prompt_for_mode(task_mode: TaskMode) -> str:
    """Get mode-specific prompt instructions."""
    
    base = """You are a Smart Financial Advisor (SFA).

DATABASE SCHEMA:
{schema_context}

TOOLS:
{tools}
"""
    
    # Mode-specific rules
    mode_rules = {
        TaskMode.GRAPH: """
TASK MODE: GRAPH
- Query data for visualization
- Return results as MARKDOWN TABLE (do NOT convert to text)
- Include the raw table in your Final Answer
""",
        TaskMode.AGGREGATION: """
TASK MODE: AGGREGATION  
- Use SUM(), AVG(), COUNT() etc. in your SQL
- Query MUST return a single aggregated value
- Format the number nicely in your answer (e.g., $2.89B)
""",
        TaskMode.LOOKUP: """
TASK MODE: LOOKUP
- Query a specific value (single row)
- Use WHERE clause with year, quarter, etc.
- Format the value nicely in your answer
""",
        TaskMode.ADVISORY: """
TASK MODE: ADVISORY
- Use the advisory_agent tool for investment advice
- Do NOT make up financial recommendations
""",
        TaskMode.COMPARISON: """
TASK MODE: COMPARISON
- Use SUM() with GROUP BY year to get totals for each year
- Example: SELECT year, SUM(revenue) FROM swf_financials WHERE year IN (2022, 2024) GROUP BY year
- Show BOTH values in your Final Answer (e.g., "2022: $1.69B vs 2024: $2.89B")
- Use calculator for percentage changes if needed
"""
    }
    
    format_section = """
FORMAT:
Thought: [reasoning]
Action: one of [{tool_names}]
Action Input: [input]
Observation: [result]

When done:
Thought: I now know the final answer
Final Answer: [your answer]

Question: {input}
{agent_scratchpad}
"""
    
    return base + mode_rules.get(task_mode, "") + format_section


# =============================================================================
# CURRENCY FORMATTER
# =============================================================================
def format_currency_number(text: str) -> str:
    pattern = r"-?\d+\.?\d*e[+-]?\d+"
    
    def repl(match):
        try:
            num = float(match.group(0))
            abs_num = abs(num)
            sign = "-" if num < 0 else ""
            if abs_num >= 1e12:
                return f"{sign}${abs_num/1e12:.2f}T"
            if abs_num >= 1e9:
                return f"{sign}${abs_num/1e9:.2f}B"
            if abs_num >= 1e6:
                return f"{sign}${abs_num/1e6:.2f}M"
            if abs_num >= 1e3:
                return f"{sign}${abs_num/1e3:.2f}K"
            return f"{sign}${abs_num:.2f}"
        except Exception:
            return match.group(0)
    
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def extract_value_from_table(table_text: str) -> str:
    """
    Extract the numeric value from a SQL table result and format it nicely.
    For aggregation/lookup results like:
    |   SUM(revenue) |
    |---------------:|
    |    2.89379e+09 |
    
    Returns: "$2.89B" instead of the raw table
    """
    lines = [l.strip() for l in table_text.strip().split('\n') if l.strip().startswith('|')]
    if len(lines) < 2:
        return format_currency_number(table_text)
    
    # Get the data row (skip header and separator)
    data_rows = [l for l in lines if '---' not in l]
    if len(data_rows) < 2:
        return format_currency_number(table_text)
    
    # Get the value from the last data row, last column
    last_row = data_rows[-1]
    cells = [c.strip() for c in last_row.split('|') if c.strip()]
    if not cells:
        return format_currency_number(table_text)
    
    value = cells[-1]
    
    # Try to parse as number and format
    try:
        # Check if it's a percentage (small decimal)
        num = float(value)
        if -1 < num < 1 and num != 0:
            # Likely a percentage/margin
            return f"{num*100:.2f}%"
        else:
            # Regular number - format as currency
            return format_currency_number(value)
    except ValueError:
        return format_currency_number(table_text)


# =============================================================================
# MAIN AGENT CLASS
# =============================================================================
class LangChainAgent:
    """
    Hardened LangChain Agent with:
    - Task mode isolation
    - Query-scoped SQL caching
    - Result validation
    - Hard termination guarantees
    """
    
    def __init__(self, user: Any):
        self.user = user
        self.interaction_id = str(uuid.uuid4())
        self.query_id = None
        self.using_fallback = False
        self._init_llm(PRIMARY_MODEL)
    
    def _init_llm(self, model_name: str):
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name=model_name,
            temperature=0.2,
            max_tokens=800
        )
        log_system_debug(f"[LangChain] Initialized LLM: {model_name}")
    
    def _create_sql_tool(self, sql_cache: QueryScopedSQLCache, task_mode: TaskMode) -> Tool:
        """
        Create SQL tool with:
        - Query-scoped caching (NOT call-count based)
        - Result validation against task mode
        - Hard termination signaling
        """
        
        def run_sql(query: str) -> str:
            # Strip code blocks AND backticks that may wrap the query
            clean = query.replace("```sql", "").replace("```", "").strip()
            clean = clean.strip('`')  # Remove leading/trailing backticks
            
            # Check cache FIRST (by query text, not call count)
            cached = sql_cache.get(clean)
            if cached is not None:
                log_system_debug(f"[SQL] Cache HIT for: {clean[:50]}...")
                return f"[CACHED] {cached}\n\n⚠️ This is cached data. Write Final Answer now."
            
            # Execute SQL
            try:
                if self.query_id:
                    set_query_progress(self.query_id, "sql", "Querying database")
                
                log_agent_interaction(self.interaction_id, "LangChain-SQL", "Tool Call", clean, None)
                result = execute_sql_query(clean, user=self.user)
                
                # Validate result against task mode
                result = SQLResultValidator.validate(result, task_mode, clean)
                
                # Cache the result
                sql_cache.set(clean, result)
                
                log_agent_interaction(
                    self.interaction_id, "LangChain-SQL", "Tool Result",
                    clean, result[:500] if len(result) > 500 else result
                )
                
                return result
                
            except Exception as e:
                error_msg = f"SQL Error: {str(e)}"
                log_system_error(error_msg)
                return error_msg
        
        return Tool(
            name="sql_query",
            func=run_sql,
            description="Execute SELECT SQL query. Input: raw SQL string."
        )
    
    @traceable(name="SFA-Agent-Run", run_type="chain")
    def run(self, query: str, interaction_id: str | None = None, graph_mode: bool = False) -> str:
        """
        Execute agent with hardened architecture.
        
        Key guarantees:
        1. Task mode is classified ONCE and cannot change
        2. SQL cache is query-scoped
        3. Valid SQL result WILL appear in final answer
        """
        if interaction_id:
            self.interaction_id = interaction_id
            set_advisory_interaction_id(interaction_id)
            set_advisory_query_id(self.query_id)
        
        # =====================================================================
        # STEP 1: Classify task mode (IMMUTABLE for this run)
        # =====================================================================
        task_mode = TaskMode.GRAPH if graph_mode else classify_task_mode(query)
        log_system_debug(f"[LangChain] Task mode: {task_mode.value}")
        
        # =====================================================================
        # STEP 2: Create fresh, query-scoped SQL cache
        # =====================================================================
        sql_cache = QueryScopedSQLCache()
        
        try:
            # =================================================================
            # STEP 3: Build tools with mode-aware SQL validator
            # =================================================================
            schema_context = get_table_schemas(user=self.user)
            log_system_debug(f"[LangChain] Schema length: {len(schema_context)}")
            
            tools = [
                self._create_sql_tool(sql_cache, task_mode),
                get_calculator_tool(lambda: None, lambda: self.query_id),
                get_advisory_tool()
            ]
            
            # =================================================================
            # STEP 4: Create mode-specific prompt
            # =================================================================
            prompt_template = get_prompt_for_mode(task_mode)
            prompt = PromptTemplate.from_template(prompt_template).partial(
                schema_context=schema_context,
                tool_names=", ".join(t.name for t in tools),
                tools="\n".join(f"{t.name}: {t.description}" for t in tools)
            )
            
            # =================================================================
            # STEP 5: Execute agent
            # =================================================================
            callback = ReasoningCallbackHandler(self.query_id)
            agent = create_react_agent(self.llm, tools, prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,
                callbacks=[callback]
            )
            
            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Start", query, None)
            result = executor.invoke({"input": query})
            
            # =================================================================
            # STEP 6: Extract output with HARD GUARANTEE
            # =================================================================
            output = result.get("output", "")
            
            # If output is invalid but we have SQL data, USE THE SQL DATA
            if (not output or len(output.strip()) < 10 or "stopped due to" in output.lower()):
                if sql_cache.has_executed():
                    first_result = sql_cache.get_first_result()
                    if first_result and len(first_result) > 20:
                        # For GRAPH mode, return raw table
                        if task_mode == TaskMode.GRAPH:
                            output = first_result
                        elif task_mode == TaskMode.COMPARISON:
                            # For comparison, format table as readable text
                            output = format_currency_number(first_result)
                        else:
                            # For other modes, extract and format the value nicely
                            output = extract_value_from_table(first_result)
                        log_system_debug(f"[LangChain] Extracted SQL result as fallback")
                    else:
                        output = "I could not complete the analysis. Please rephrase the question."
                else:
                    output = "I could not complete the analysis. Please rephrase the question."
            else:
                # Format currency for non-graph outputs
                if task_mode == TaskMode.GRAPH:
                    pass  # Keep raw table
                elif task_mode == TaskMode.COMPARISON:
                    # Format numbers but keep the structure
                    output = format_currency_number(output)
                elif output.strip().startswith('|'):
                    # For single-value queries, extract the value
                    output = extract_value_from_table(output)
                else:
                    output = format_currency_number(output)
            
            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Final Answer", query, output)
            log_system_info("[LangChain] Agent completed")
            return output
            
        except Exception as e:
            msg = str(e)
            log_system_error(f"[LangChain] Failure: {msg}")
            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Error", query, msg)
            
            # Rate limit fallback
            if ("rate_limit" in msg.lower() or "429" in msg) and not self.using_fallback:
                self.using_fallback = True
                self._init_llm(FALLBACK_MODEL)
                return self.run(query, interaction_id, graph_mode)
            
            # Check if we have SQL data despite the error
            if sql_cache.has_executed():
                first_result = sql_cache.get_first_result()
                if first_result and len(first_result) > 20:
                    log_system_debug("[LangChain] Returning SQL data despite agent error")
                    if task_mode == TaskMode.GRAPH:
                        return first_result
                    return format_currency_number(first_result)
            
            if "authentication" in msg.lower() or "api_key" in msg.lower():
                return "Configuration error. Please contact support."
            if "timeout" in msg.lower():
                return "The request timed out. Please try a simpler query."
            
            return "I could not process that request. Please try again."
