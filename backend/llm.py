"""
LLM Chain-of-Tables Module
==========================
Executes Chain-of-Tables reasoning loop for SQL generation and execution.
Supports user-specific database queries for multi-tenant isolation.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.tools.sql_tools import execute_sql_query, get_table_schemas
from backend.sfa_logger import log_system_debug, log_system_error
import re

MODEL = get_model("worker")

CHAIN_OF_TABLES_PROMPT = """
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


def run_chain_of_tables(question: str, model: str = None, user=None) -> str:
    """
    Executes the Chain-of-Tables reasoning loop.
    
    Generates SQL from natural language, executes it, and returns formatted results.
    
    Args:
        question: User's question or instruction
        model: Optional model override
        user: Optional User model instance for tenant-specific queries
        
    Returns:
        SQL query + database results, or error message
    """
    if model is None:
        model = MODEL
    
    # REQUIRE user-specific database - no fallback
    schema = get_table_schemas(user=user)
    
    # Debug logging
    log_system_debug(f"[LLM] User: {user.id if user else 'None'}, db_connected: {user.db_is_connected if user else 'N/A'}")
    log_system_debug(f"[LLM] Schema retrieved: {schema[:200] if schema else 'EMPTY'}...")
    
    # Build dynamic schema context
    if user and user.db_is_connected:
        # User has their own database - use dynamic schema
        dynamic_schema = f"""DATABASE SCHEMA (User's Connected Database):
{schema}

IMPORTANT: Query ONLY the tables and columns shown above. These are the user's actual tables."""
    else:
        # No database connected - return error
        return "Error: No database connected. Please connect a database in Settings first."
    
    sql_generation_prompt = f"""You are an expert SQL generator for a data analytics database.

IMPORTANT CONTEXT:
- Generate SQL for the user's connected database.
- Use ONLY the columns and tables shown in the schema below.
- Be flexible with table/column names - they may vary by dataset.

{dynamic_schema}

RULES:
- Do NOT invent columns - use ONLY columns listed above.
- Use ORDER BY for time series if date/time columns exist.
- Handle different data types appropriately.

OUTPUT:
Return ONLY valid SQL wrapped in ```sql```.

Question: {question}
"""
    
    try:
        # Generate SQL
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": sql_generation_prompt}],
            model=model,
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Strip thinking tags from models that expose reasoning (like DeepSeek)
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        
        # Robust Cleaning
        sql_query = content
        if "```" in content:
            # Extract content between triple backticks
            match = re.search(r"```(?:sql)?(.*?)```", content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
        else:
            # Fallback: strict word boundary search for SELECT
            match = re.search(r"(\bSELECT\b.*?;)", content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
            else:
                # If no semicolon, just take from strict SELECT to end
                match = re.search(r"(\bSELECT\b.*)", content, re.DOTALL | re.IGNORECASE)
                if match:
                     sql_query = match.group(1).strip()
                
            # Double check for markdown artifacts at the end
            sql_query = sql_query.split("\n\n")[0]
            
        # Strip trailing semicolon for driver compatibility
        sql_query = sql_query.strip().rstrip(";")
            
        log_system_debug(f"Generated SQL: {sql_query}")
        
        # Execute SQL - user-specific if user provided
        query_result = execute_sql_query(sql_query, user=user)
        
        # Safety: Final truncation if string is still massive
        if len(query_result) > 15000:
            query_result = query_result[:12000] + "\n...(Truncated for token limits)"
            
        log_system_debug(f"DB Result Sample: {query_result[:200]}...")
        
        # Handle Empty Data Explicitly
        if not query_result or "[]" in query_result or query_result.strip() == "":
            log_system_debug("NO DATA FOUND from SQL execution.")
            return f"SQL Query Used:\n{sql_query}\n\nNO_DATA_FOUND_SIGNAL"
            
        # Return raw result directly with SQL query for debugging
        return f"SQL Query Used:\n{sql_query}\n\nDatabase Results:\n{query_result}"
        
    except Exception as e:
        log_system_error(f"Chain-of-Tables Error: {e}")
        return f"Error in Chain-of-Tables: {e}"

