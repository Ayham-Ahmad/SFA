import os
import uuid
import re
from typing import Any
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

MAX_TOOL_RETRIES = 2
PRIMARY_MODEL = get_model("default")
FALLBACK_MODEL = get_model("fast")

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

AGENT_SYSTEM_PROMPT = """You are a Smart Financial Advisor (SFA).

CRITICAL: USE THE DATABASE SCHEMA BELOW - DO NOT query sqlite_master!

DATABASE SCHEMA:
{schema_context}

TOOLS:
{tools}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL AGGREGATION RULES (MUST FOLLOW):
═══════════════════════════════════════════════════════════════════════════════

1. If the question asks for TOTAL, SUM, AVERAGE, MIN, MAX, or COUNT:
   - You MUST compute it directly in SQL using SUM(), AVG(), MIN(), MAX(), COUNT()
   - DO NOT use the calculator for database totals
   - The SQL query should return the final computed number

2. The calculator tool is ONLY for:
   - Percentages (e.g., growth rate = (new - old) / old * 100)
   - Ratios (e.g., debt-to-equity)
   - Simple math on FINAL numbers already computed by SQL

3. NEVER calculate database totals using the calculator

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE STOP RULE (NON-NEGOTIABLE):
═══════════════════════════════════════════════════════════════════════════════

After you receive data from sql_query:
- If you have the answer, you MUST immediately write Final Answer
- You are NOT allowed to call ANY tool again (NOT calculator, NOT sql_query, NOT advisory)
- Go directly to Final Answer

═══════════════════════════════════════════════════════════════════════════════
TERMINATION RULE (CRITICAL):
═══════════════════════════════════════════════════════════════════════════════

If you write "Thought: I now know the final answer"
and then call ANY tool, your answer will be considered INVALID.

After "Thought: I now know the final answer", you MUST write "Final Answer:" immediately.

═══════════════════════════════════════════════════════════════════════════════
CALCULATOR INPUT RULES:
═══════════════════════════════════════════════════════════════════════════════

- Calculator input MUST be a pure Python arithmetic expression
- ONLY numbers and operators (+, -, *, /, **)
- NO variables (df, table, rows, columns, data)
- NO function calls except basic math

VALID calculator inputs:
  7.1e7 + 2.5e7
  (500000 - 400000) / 400000 * 100
  204964000 / 1000000

INVALID calculator inputs:
  df['net_income'].sum()
  data.loc[year == 2023]
  rows['revenue'].mean()

═══════════════════════════════════════════════════════════════════════════════
GRAPH/PLOT RULES (IMPORTANT):
═══════════════════════════════════════════════════════════════════════════════

If the question asks to PLOT, CHART, GRAPH, or VISUALIZE data:
- Your Final Answer MUST include the SQL result as a MARKDOWN TABLE
- Do NOT convert the table to bullet points or prose
- Include the raw table data so a graph can be generated

CORRECT for graph query:
Final Answer: 
| quarter | revenue |
|---------|---------|
| 1 | 498825000 |
| 2 | 526000000 |

WRONG for graph query:
Final Answer: The quarterly revenue is: Q1: $498M, Q2: $526M...

═══════════════════════════════════════════════════════════════════════════════
FORMAT (use this exact format):
═══════════════════════════════════════════════════════════════════════════════

Thought: [your reasoning]
Action: one of [{tool_names}]
Action Input: [tool input]
Observation: [tool result - this will be filled by the system]
... (repeat if needed, but minimize iterations)

When done:
Thought: I now know the final answer
Final Answer: [your complete answer to the user]

═══════════════════════════════════════════════════════════════════════════════
CORRECT EXAMPLE - TOTAL NET INCOME:
═══════════════════════════════════════════════════════════════════════════════

Question: What was the total net income in 2023?

Thought: I need the total net income for 2023. I will use SUM() in SQL to compute this directly.
Action: sql_query
Action Input: SELECT SUM(net_income) AS total_net_income FROM swf_financials WHERE year = 2023
Observation: | total_net_income |
             | 204964000        |

Thought: I now know the final answer
Final Answer: The total net income in 2023 was $204.96 million.

═══════════════════════════════════════════════════════════════════════════════

Question: {input}
{agent_scratchpad}
"""

class LangChainAgent:
    def __init__(self, user: Any):
        self.user = user
        self.interaction_id = str(uuid.uuid4())
        self.current_data_context = None
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

    def _get_sql_tool(self) -> Tool:
        sql_call_count = 0
        cached_result = None

        def run(query: str) -> str:
            nonlocal sql_call_count, cached_result
            clean_query = query.replace("```sql", "").replace("```", "").strip()
            sql_call_count += 1
            if sql_call_count > 1 and cached_result:
                return f"⚠️ SQL already executed. USE THIS RESULT:\n{cached_result}\n\n⛔ Write Final Answer now."
            for attempt in range(MAX_TOOL_RETRIES):
                try:
                    if self.query_id:
                        set_query_progress(self.query_id, "sql", "Querying database")
                    log_agent_interaction(self.interaction_id, "LangChain-SQL", "Tool Call", clean_query, None)
                    result = execute_sql_query(clean_query, user=self.user)
                    cached_result = result
                    log_agent_interaction(
                        self.interaction_id,
                        "LangChain-SQL",
                        "Tool Result",
                        clean_query,
                        result[:500] if len(result) > 500 else result
                    )
                    return result
                except Exception as e:
                    log_system_error(f"SQL attempt failed: {e}")
            raise RuntimeError("SQL execution failed")

        return Tool(
            name="sql_query",
            func=run,
            description="Executes a SELECT SQL query. Input: raw SQL string."
        )

    @traceable(name="SFA-Agent-Run", run_type="chain")
    def run(self, query: str, interaction_id: str | None = None, graph_mode: bool = False) -> str:
        if interaction_id:
            self.interaction_id = interaction_id
            set_advisory_interaction_id(interaction_id)
            set_advisory_query_id(self.query_id)

        try:
            schema_context = get_table_schemas(user=self.user)
            log_system_debug(f"[LangChain] Schema length: {len(schema_context)}")

            tools = [
                self._get_sql_tool(),
                get_calculator_tool(lambda: self.current_data_context, lambda: self.query_id),
                get_advisory_tool()
            ]

            prompt = PromptTemplate.from_template(AGENT_SYSTEM_PROMPT).partial(
                schema_context=schema_context,
                tool_names=", ".join(t.name for t in tools),
                tools="\n".join(f"{t.name}: {t.description}" for t in tools)
            )

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

            output = result.get("output", "")
            # Fallback: Extract from intermediate steps if output is empty or agent stopped
            if not output or len(output.strip()) < 10 or "stopped due to" in output.lower():
                steps = result.get("intermediate_steps", [])
                observations = []
                for _, obs in steps:
                    s = str(obs)
                    if len(s) > 30 and "error" not in s.lower():
                        observations.append(s)
                if observations:
                    output = max(observations, key=len)
                else:
                    output = "I could not complete the analysis. Please rephrase the question."

            output = format_currency_number(output)
            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Final Answer", query, output)
            log_system_info("[LangChain] Agent completed")
            return output

        except Exception as e:
            msg = str(e)
            log_system_error(f"[LangChain] Failure: {msg}")
            log_agent_interaction(self.interaction_id, "LangChain-Agent", "Error", query, msg)

            if ("rate_limit" in msg.lower() or "429" in msg) and not self.using_fallback:
                self.using_fallback = True
                self._init_llm(FALLBACK_MODEL)
                return self.run(query, interaction_id, graph_mode)

            if "authentication" in msg.lower() or "api_key" in msg.lower():
                return "Configuration error. Please contact support."
            if "timeout" in msg.lower():
                return "The request timed out. Please try a simpler query."

            return "I could not process that request. Please try again."
