"""
LangChain Agent V3 - Hardened Architecture
=========================================
"""

import os
import uuid
import re
from typing import Any, Dict, Optional
from enum import Enum

from langchain_groq import ChatGroq
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler

from backend.core.logger import (
    log_system_info,
    log_system_error,
    log_system_debug,
    log_agent_interaction,
)
from backend.tools.sql_tools import execute_sql_query, get_table_schemas
from backend.tools.calculator import get_calculator_tool
from backend.tools.advisory_tool import (
    get_advisory_tool,
    set_advisory_interaction_id,
    set_advisory_query_id,
)
from backend.pipeline.progress import set_query_progress
from backend.utils.llm_client import get_model, increment_api_counter

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


PRIMARY_MODEL = get_model("default")
FALLBACK_MODEL = get_model("fast")


class TaskMode(Enum):
    GRAPH = "graph"
    AGGREGATION = "agg"
    LOOKUP = "lookup"
    ADVISORY = "advisory"
    COMPARISON = "comparison"


def classify_task_mode(query: str) -> TaskMode:
    """Classify user query into ONE immutable task mode."""
    # Extract just the user's current query if context is present
    # Format: "Context:\n...\nUser Query: actual question"
    if "User Query:" in query:
        query = query.split("User Query:")[-1].strip()
    
    q = query.lower()

    if any(k in q for k in ["plot", "chart", "graph", "visualiz", "trend", "show me", "display"]):
        return TaskMode.GRAPH

    if any(k in q for k in ["should i", "recommend", "advice", "strategy", "invest", "danger"]):
        return TaskMode.ADVISORY

    if any(k in q for k in ["compare", "vs", "versus", "between", "difference"]):
        return TaskMode.COMPARISON

    if any(k in q for k in ["total", "sum", "average", "avg", "count", "how many", "all time"]):
        return TaskMode.AGGREGATION

    return TaskMode.LOOKUP


class SQLResultValidator:
    """Validates SQL results against expected task mode."""
    
    @staticmethod
    def validate(result: str, task_mode: TaskMode, sql_query: str) -> str:
        if not result or "Error" in result:
            return result

        lines = [l for l in result.splitlines() if l.strip().startswith("|")]
        if len(lines) < 2:
            return result

        data_rows = [l for l in lines if "---" not in l][1:]
        row_count = len(data_rows)

        if task_mode == TaskMode.AGGREGATION and row_count > 1:
            log_system_error(f"[Validator] AGGREGATION mode returned {row_count} rows")

        if task_mode == TaskMode.GRAPH and row_count < 2:
            log_system_debug(f"[Validator] GRAPH mode returned insufficient rows ({row_count})")

        return result

    @staticmethod
    def normalize_sql(sql: str) -> str:
        """Normalize SQL for cache key comparison."""
        sql = " ".join(sql.lower().split())
        return sql.rstrip(";").strip()


class QueryScopedSQLCache:
    """SQL cache keyed by normalized query text."""
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._first_result: Optional[str] = None
        self._executed = False

    def get(self, sql: str) -> Optional[str]:
        return self._cache.get(SQLResultValidator.normalize_sql(sql))

    def set(self, sql: str, result: str):
        key = SQLResultValidator.normalize_sql(sql)
        self._cache[key] = result
        if not self._executed:
            self._first_result = result
            self._executed = True

    def has_executed(self) -> bool:
        return self._executed

    def get_first_result(self) -> Optional[str]:
        return self._first_result


class ReasoningCallbackHandler(BaseCallbackHandler):
    """Sends agent reasoning steps to frontend thinking box and tracks API calls."""
    
    def __init__(self, query_id: Optional[str] = None):
        self.query_id = query_id
        self.step_count = 0  # Track number of reasoning steps

    def on_llm_start(self, serialized, prompts, **kwargs):
        if self.query_id:
            set_query_progress(self.query_id, "reasoning", "Thinking...")

    def on_llm_end(self, response, **kwargs):
        # Extract token usage from LLMResult
        tokens = 0
        if hasattr(response, 'llm_output') and response.llm_output:
            usage = response.llm_output.get('token_usage', {})
            tokens = usage.get('total_tokens', 0)
        
        # Always increment the counter for each LLM call
        increment_api_counter(PRIMARY_MODEL, tokens)

        if not self.query_id or not response.generations:
            return

        text = response.generations[0][0].text or ""
        match = re.search(r"Thought:\s*(.+?)(?=\n|Action:|$)", text, re.DOTALL)

        if match:
            thought = match.group(1).strip()[:150]
        else:
            thought = text.strip().split("\n")[0][:100]
            
        if thought:
            set_query_progress(self.query_id, "reasoning", f"💭 {thought}")
            log_system_debug(f"[Callback] Thought: {thought}")

    def on_agent_action(self, action, **kwargs):
        # Increment step count for each action taken
        self.step_count += 1
        if self.query_id:
            set_query_progress(self.query_id, "reasoning", f"🔧 Using {action.tool}...")

    def on_tool_end(self, output, **kwargs):
        if self.query_id:
            out = str(output)[:80]
            set_query_progress(self.query_id, "reasoning", f"📊 {out}")

def get_prompt_for_mode(task_mode: TaskMode) -> str:
    """Get prompt - now uses unified prompt for all modes, letting LLM decide tools."""
    return """You are a Smart Financial Advisor (SFA) with access to a financial database.

DATABASE SCHEMA:
{schema_context}

TOOLS:
{tools}

HOW TO USE TOOLS:
- sql_query: Query the database for financial data (revenue, income, margins, etc.)
- calculator: Perform math calculations on numbers
- advisory: Get investment advice and recommendations

IMPORTANT GUIDELINES:
1. For questions about specific data (revenue, income, etc.) → use sql_query FIRST
2. For questions asking for advice/recommendations → get relevant data with sql_query FIRST, then use advisory
3. For calculations on data → get data with sql_query, then use calculator if needed
4. Always base your advice on ACTUAL data from the database, not assumptions

FORMAT (follow strictly):
Thought: your reasoning about what you need to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input for the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation cycle can repeat N times)
Thought: I now know the final answer
Final Answer: your answer here

CRITICAL RULES:
1. You MUST provide a Final Answer after getting data from a tool
2. Do NOT repeat queries you already made - if you see [CACHED], answer immediately
3. Your final response MUST start with exactly "Final Answer: " (including the space after the colon)
4. Omitting the "Final Answer: " prefix will cause processing to fail
5. If SQL returns a formatted value like "$2.89B" or "$814.08M", use it directly as the Final Answer - do NOT use calculator to convert it
6. NEVER use "Action: None" - when you have the data you need, go directly to "Final Answer:"
7. For GRAPH/CHART/VISUALIZATION requests: Return the SQL table result DIRECTLY as your Final Answer - do NOT summarize, calculate averages, or transform the data. The table format is required for rendering charts.
8. If a table name is a NUMBER (e.g., 6, 123), you MUST wrap it in square brackets: SELECT * FROM [6]. Using quotes or backticks will cause errors.
9. ADVISORY TOOL RULES:
   a) When calling advisory, you MUST include the FULL SQL data in your Action Input. Example: "User asks about investment strategy. Here is the data: [paste the full table]"
   b) After advisory returns, copy its ENTIRE structured response as your Final Answer. Do NOT summarize or condense the advisory output.

Begin!

Question: {input}
Thought: {agent_scratchpad}
"""


def format_currency_number(text: str) -> str:
    """Format scientific notation numbers as currency."""
    pattern = r"-?\d+\.?\d*e[+-]?\d+"

    def repl(m):
        n = float(m.group(0))
        a = abs(n)
        s = "-" if n < 0 else ""
        if a >= 1e9:
            return f"{s}${a/1e9:.2f}B"
        if a >= 1e6:
            return f"{s}${a/1e6:.2f}M"
        return f"{s}${a:.2f}"

    return re.sub(pattern, repl, text, flags=re.I)


def extract_value_from_table(table: str) -> str:
    """Extract numeric value from SQL table result and format nicely."""
    lines = [l for l in table.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return format_currency_number(table)

    row = [c.strip() for c in lines[-1].split("|") if c.strip()]
    return format_currency_number(row[-1]) if row else table


class LangChainAgent:
    """Hardened LangChain Agent with task mode isolation and query-scoped caching."""
    
    def __init__(self, user: Any):
        self.user = user
        self.interaction_id = str(uuid.uuid4())
        self.query_id: Optional[str] = None
        self.using_fallback = False
        self._init_llm(PRIMARY_MODEL)

    def _init_llm(self, model: str, callback_handler=None):
        log_system_debug(f"[LangChain] Initialized LLM: {model}")
        callbacks = [callback_handler] if callback_handler else None
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name=model,
            temperature=0.2,
            max_tokens=800,
            callbacks=callbacks,
        )

    def _create_sql_tool(self, cache: QueryScopedSQLCache, mode: TaskMode) -> Tool:
        """Create SQL tool with query-scoped caching and validation."""
        
        def run_sql(sql: str) -> str:
            # Strip markdown wrapping
            sql = sql.replace("```sql", "").replace("```", "").strip("` ")

            # Check cache first
            cached = cache.get(sql)
            if cached:
                log_system_debug(f"[SQL] Cache hit for: {sql[:50]}...")
                return f"[CACHED] {cached}\n\n⚠️ This is cached data. Write Final Answer now."

            # Execute query
            if self.query_id:
                set_query_progress(self.query_id, "sql", "Querying database...")
            result = execute_sql_query(sql, user=self.user)
            result = SQLResultValidator.validate(result, mode, sql)
            cache.set(sql, result)
            
            # --- SIMULATION: Trigger token limit AFTER SQL executes ---
            try:
                from evaluation.sfa_evaluator import SIMULATE_RATE_LIMIT_AT_QUERY
                if SIMULATE_RATE_LIMIT_AT_QUERY > 0 and self.query_id:
                    import re
                    match = re.search(r'(\d+)', str(self.query_id))
                    if match:
                        current_query_num = int(match.group(1))
                        if current_query_num >= SIMULATE_RATE_LIMIT_AT_QUERY:
                            log_system_info(f"[SIMULATION] Token limit triggered after SQL returned data")
                            raise Exception("429 tokens_per_day limit_exceeded - SIMULATED")
            except ImportError:
                pass
            
            return result

        return Tool(
            name="sql_query",
            func=run_sql,
            description="Execute SELECT SQL query. Input: raw SQL string.",
        )

    @traceable(name="SFA-Agent-Run", run_type="chain")
    def run(self, query: str, interaction_id=None, graph_mode=False, query_id=None) -> str:
        """
        Execute agent with hardened architecture.
        
        Key guarantees:
        1. Task mode is classified ONCE and cannot change
        2. SQL cache is query-scoped
        3. Valid SQL result WILL appear in final answer
        """
        self.query_id = query_id
        if interaction_id:
            self.interaction_id = interaction_id
            set_advisory_interaction_id(interaction_id)
            set_advisory_query_id(query_id)

        # Classify task mode (IMMUTABLE)
        mode = TaskMode.GRAPH if graph_mode else classify_task_mode(query)
        log_system_debug(f"[LangChain] Task mode: {mode.value}")
        
        # Fresh cache per query
        cache = QueryScopedSQLCache()

        try:
            # Get schema
            schema = get_table_schemas(user=self.user)
            log_system_debug(f"[LangChain] Schema length: {len(schema)}")
            
            # Build tools
            tools = [
                self._create_sql_tool(cache, mode),
                get_calculator_tool(lambda: None, lambda: query_id),
                get_advisory_tool(),
            ]

            # Build prompt
            prompt = PromptTemplate.from_template(
                get_prompt_for_mode(mode)
            ).partial(
                schema_context=schema,
                tool_names=", ".join(t.name for t in tools),
                tools="\n".join(f"{t.name}: {t.description}" for t in tools),
            )

            # Create and execute agent
            handler = ReasoningCallbackHandler(query_id)  # Create handler first
            
            # Reinitialize LLM with callback so all API calls are counted
            self._init_llm(PRIMARY_MODEL if not self.using_fallback else FALLBACK_MODEL, handler)
            
            agent = create_react_agent(self.llm, tools, prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=20,
                handle_parsing_errors=True,
                verbose=True,
                callbacks=[handler],
            )

            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Start", query, None)
            
            # Run the agent
            response_dict = executor.invoke({"input": query})
            output = response_dict["output"].strip()
            
            # Get step count from callback
            step_count = handler.step_count
            
            log_system_debug(f"Agent finished in {step_count} steps. Output: {output[:50]}...")
            
            # Fallback: use cached SQL result if output is empty
            if not output and cache.has_executed():
                raw = cache.get_first_result()
                log_system_debug("[LangChain] Using cached SQL result as fallback")
                output = raw if mode == TaskMode.GRAPH else format_currency_number(raw)
                return {
                    "output": output,
                    "steps": step_count
                }

            # Format output based on mode
            if mode == TaskMode.GRAPH:
                return output
            elif output.strip().startswith('|'):
                return extract_value_from_table(output)
            else:
                return format_currency_number(output)

        except Exception as e:
            error_msg = str(e).lower()
            log_system_error(f"[LangChain] Error: {error_msg}")
            
            # Rate/Token limit handling - graceful degradation WITH fallback model
            # Catches both RPM (requests per minute) and TPD (tokens per day) limits
            is_limit_error = any(x in error_msg for x in ["429", "rate_limit", "rate limit", "tokens_per_day", "limit_exceeded"])
            if is_limit_error:
                log_system_info("[LangChain] API limit hit - using fallback model for cached data")
                
                # If we have cached SQL data, use small model to format it nicely
                if cache.has_executed():
                    cached_result = cache.get_first_result()
                    log_system_debug(f"[LangChain] Using {FALLBACK_MODEL} to format cached data")
                    
                    try:
                        # Use the small/fast model to generate natural language response
                        from groq import Groq
                        fallback_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                        
                        format_prompt = f"""You are a data formatter. Summarize ONLY the data provided below. Do NOT add any analysis, predictions, or information from your own knowledge.

User Question: {query}

Data:
{cached_result}

Rules:
1. Only state facts directly visible in the data
2. Keep it brief (2-3 sentences max)
3. Do not calculate percentages or trends unless they are in the data
4. Do not give advice or recommendations"""

                        fallback_response = fallback_client.chat.completions.create(
                            messages=[{"role": "user", "content": format_prompt}],
                            model=FALLBACK_MODEL,
                            temperature=0.1,  # Lower temperature for more factual output
                            max_tokens=200
                        )
                        
                        formatted = fallback_response.choices[0].message.content.strip()
                        # Add notice that reasoning model is busy
                        formatted = formatted + "\n\n---\nℹ️ *Note: The reasoning model is currently busy. This is a simplified response. Please try again later for detailed analysis.*"
                        log_system_info(f"[LangChain] Fallback model generated response successfully")
                        return {"output": formatted, "steps": 0}
                        
                    except Exception as fallback_error:
                        log_system_error(f"[LangChain] Fallback model also failed: {fallback_error}")
                        # Last resort: Python formatting
                        if mode == TaskMode.GRAPH:
                            return {"output": cached_result, "steps": 0}
                        else:
                            formatted = extract_value_from_table(cached_result) if cached_result.strip().startswith('|') else format_currency_number(cached_result)
                            return {"output": formatted, "steps": 0}
                
                # No cached data - return busy message
                return {"output": "The AI service is currently busy. Please try again in a few minutes.", "steps": 0}

            return "I could not process that request. Please try again."
