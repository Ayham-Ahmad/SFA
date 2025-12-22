from groq import Groq
import os
from .tools.sql_tools import execute_sql_query, get_table_schemas
from dotenv import load_dotenv
import re
from backend.sfa_logger import log_system_debug, log_system_error
from backend.config import TESTING

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "qwen/qwen3-32b"

CHAIN_OF_TABLES_PROMPT_INLINE = """
You are a Financial Analyst.

You are given tabular financial results derived from validated SQL queries.

Your task:
- Interpret the data accurately
- Explain trends, comparisons, or changes
- Do NOT invent values
- Do NOT mention SQL, databases, or tables

Rules:
- Be precise but concise
- Use plain financial language
- If data is missing or unclear, say so explicitly

User question: {question}
Data:
{context}
"""

if TESTING:
    from backend.prompts import CHAIN_OF_TABLES_PROMPT
else:
    CHAIN_OF_TABLES_PROMPT = CHAIN_OF_TABLES_PROMPT_INLINE


def run_chain_of_tables(question: str, model: str = MODEL) -> str:
    """
    Executes the Chain-of-Tables reasoning loop.
    Note: For this simplified implementation, we will do a single-turn "Think-and-Query" 
    or rely on the LLM to generate the SQL, we execute it, and then feed it back.
    """
    schema = get_table_schemas()
    
    # Import tag information from sql_loader
    from backend.ingestion.sql_loader import get_tags_for_prompt
    available_tags = get_tags_for_prompt()
    
    # Step 1: Ask LLM to generate SQL
    if TESTING:
        from backend.prompts import SQL_GENERATION_PROMPT
        # Note: prompts.py SQL_GENERATION_PROMPT expects {schema}, {available_tags}, and {question}
        sql_generation_prompt = SQL_GENERATION_PROMPT.format(
            schema=schema,
            available_tags=available_tags,
            question=question
        )
    else:
        # Get dynamic schema from database
        from backend.schema_utils import get_full_schema_context
        dynamic_schema = get_full_schema_context()
        
        sql_generation_prompt = f"""You are an expert SQL generator for a financial analytics database.

IMPORTANT CONTEXT:
- The data represents ONE virtual, market-level entity.
- There are NO individual companies.
- Queries must be time-based (year / quarter / trade_date).

{dynamic_schema}

RULES:
- Do NOT invent columns - use ONLY columns listed above.
- Do NOT reference companies.
- Use ORDER BY for time series.
- For stock prices, use market_daily_data (open_price, close_price, high_price, low_price).
- For financial data, use swf_financials (revenue, net_income, etc).

OUTPUT:
Return ONLY valid SQL wrapped in ```sql```.

Question: {question}
"""
    
    try:
        # Generate SQL
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": sql_generation_prompt}],
            model=model,
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Robust Cleaning
        sql_query = content
        if "```" in content:
            # Extract content between triple backticks
            match = re.search(r"```(?:sql)?(.*?)```", content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
        else:
            # Fallback: strict word boundary search for SELECT
            # Prevents capturing "selecting..." from normal text
            match = re.search(r"(\bSELECT\b.*?;)", content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
            else:
                # If no semicolon, just take from strict SELECT to end
                match = re.search(r"(\bSELECT\b.*)", content, re.DOTALL | re.IGNORECASE)
                if match:
                     sql_query = match.group(1).strip()
                
            # Double check for markdown artifacts at the end if user forgot code blocks
            sql_query = sql_query.split("\n\n")[0] # Stop at double newline often used before explanation
            
        # Strip trailing semicolon for driver compatibility
        sql_query = sql_query.strip().rstrip(";")
            
        log_system_debug(f"Generated SQL: {sql_query}")
        
        # Execute SQL
        query_result = execute_sql_query(sql_query)
        # Safety: Final truncation if string is still massive
        if len(query_result) > 15000:
            query_result = query_result[:12000] + "\n...(Truncated for token limits)"
            
        log_system_debug(f"DB Result Sample: {query_result[:200]}...")
        
        # KEY CHANGE: Handle Empty Data Explicitly
        if not query_result or "[]" in query_result or query_result.strip() == "":
            log_system_debug("NO DATA FOUND from SQL execution.")
            return f"SQL Query Used:\n{sql_query}\n\nNO_DATA_FOUND_SIGNAL"
            
        # KEY CHANGE: Return raw result directly with SQL query for debugging.
        # The Auditor will handle the synthesis.
        return f"SQL Query Used:\n{sql_query}\n\nDatabase Results:\n{query_result}"
        
    except Exception as e:
        log_system_error(f"Chain-of-Tables Error: {e}")
        return f"Error in Chain-of-Tables: {e}"
