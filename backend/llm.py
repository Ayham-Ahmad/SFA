from groq import Groq
import os
from .tools.sql_tools import execute_sql_query, get_table_schemas
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "qwen/qwen3-32b"

# ============================================
# TESTING FLAG imported from config
# ============================================
from backend.config import TESTING

CHAIN_OF_TABLES_PROMPT_INLINE = """
You are a financial analyst AI capable of reasoning over tabular data using SQL.
Your goal is to answer the user's question by generating and executing SQL queries against the 'financial_data.db'.

Database Schema:
{schema}

Strategy (Chain-of-Tables):
1.  **Plan**: Break down the question into steps.
2.  **Query**: Write a SQL query to get the necessary data for the current step.
3.  **Analyze**: Look at the query result.
4.  **Refine**: If the data is insufficient, write another query.
5.  **Answer**: Synthesize the final answer based on the retrieved data.

Constraint:
- Output ONLY the final answer in a clean, readable format (Markdown).
- Do NOT show the SQL queries to the user in the final output, but use them internally.
- If you need to perform calculations, do them explicitly.

User Question: {question}
"""

if TESTING:
    from backend.prompts import CHAIN_OF_TABLES_PROMPT
    print(" ****** CHAIN_OF_TABLES_PROMPT from prompts.py for testing")
else:
    CHAIN_OF_TABLES_PROMPT = CHAIN_OF_TABLES_PROMPT_INLINE
    print(" ****** CHAIN_OF_TABLES_PROMPT original")


def run_chain_of_tables(question: str, model: str = MODEL) -> str:
    """
    Executes the Chain-of-Tables reasoning loop.
    Note: For this simplified implementation, we will do a single-turn "Think-and-Query" 
    or rely on the LLM to generate the SQL, we execute it, and then feed it back.
    """
    schema = get_table_schemas()
    
    # Import tag information from sql_loader
    from backend.ingestion.sql_loader import get_tags_for_prompt, get_companies_for_prompt
    available_tags = get_tags_for_prompt()
    sample_companies = get_companies_for_prompt()
    
    # Step 1: Ask LLM to generate SQL
    if TESTING:
        from backend.prompts import SQL_GENERATION_PROMPT
        print(" ****** SQL_GENERATION_PROMPT from prompts.py for testing")
        # Note: prompts.py SQL_GENERATION_PROMPT expects {schema}, {available_tags}, and {question}
        sql_generation_prompt = SQL_GENERATION_PROMPT.format(
            schema=schema,
            available_tags=available_tags,
            question=question
        )
    else:
        print(" ****** SQL_GENERATION_PROMPT original")
        sql_generation_prompt = f"""
    You are a precise SQL generation model (Qwen). Your ONLY job is to write a valid SQLite query.
    
    Schema:
    {schema}
    
    AVAILABLE TAGS (use exactly as shown):
    {available_tags}
    
    WELL-KNOWN COMPANY NAME MAPPINGS (USE THESE EXACT NAMES):
    - "Apple" or "AAPL" -> Use `s.name = 'APPLE INC'` (EXACT MATCH!)
    - "Microsoft" or "MSFT" -> Use `s.name = 'MICROSOFT CORP'` (EXACT MATCH!)
    - "Amazon" or "AMZN" -> Use `UPPER(s.name) LIKE 'AMAZON%'`
    - "Tesla" or "TSLA" -> Use `UPPER(s.name) LIKE 'TESLA%'`
    - "Google" or "Alphabet" or "GOOGL" -> Use `UPPER(s.name) LIKE 'ALPHABET%'`
    - "Meta" or "Facebook" or "META" -> Use `UPPER(s.name) LIKE 'META%'`
    - "Nvidia" or "NVDA" -> Use `UPPER(s.name) LIKE 'NVIDIA%'`
    
    CRITICAL RULES:
    1. **ONLY SELECT**: You are strictly forbidden from writing INSERT, UPDATE, DELETE, or DROP queries.
    2. **Currency**: Always filter `WHERE n.uom = 'USD'` when comparing monetary values.
    3. **Joins**: `numbers` (n) JOIN `submissions` (s) ON `n.adsh = s.adsh`.
    4. **Dates**: `ddate` is INTEGER YYYYMMDD. Use `BETWEEN` for ranges.
    5. **NO LIMIT**: Return ALL matching results, do NOT use LIMIT clause.
    6. **COMPANY NAME MATCHING - CRITICALLY IMPORTANT**:
       - For APPLE, NEVER use LIKE 'APPLE%' - this will match 'APPLE ISPORTS GROUP' which is WRONG!
       - For APPLE, ALWAYS use EXACT MATCH: `s.name = 'APPLE INC'`
       - For MICROSOFT, ALWAYS use EXACT MATCH: `s.name = 'MICROSOFT CORP'`
       - Only use LIKE patterns for less common companies where exact name is unknown
    7. **TAG MAPPING - IMPORTANT**:
       - For "Revenue" queries, use: `n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'` (NOT 'Revenues'!)
       - Use the exact tag names from the AVAILABLE TAGS list above
    8. **Output Format**:
       - WRAP YOUR SQL IN MARKDOWN BLOCK: ```sql ... ```
       - No explanations.
       - No conversational text.

    EXAMPLES:
    
    User: "Revenue of Apple"
    SQL: 
    ```sql
    SELECT s.name, n.value, n.ddate FROM numbers n JOIN submissions s ON n.adsh = s.adsh WHERE s.name = 'APPLE INC' AND n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' AND n.uom = 'USD' ORDER BY n.ddate DESC;
    ```
    
    User: "Apple and Microsoft revenue"
    SQL:
    ```sql
    SELECT s.name, n.value, n.ddate FROM numbers n JOIN submissions s ON n.adsh = s.adsh WHERE (s.name = 'APPLE INC' OR s.name = 'MICROSOFT CORP') AND n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' AND n.uom = 'USD' ORDER BY n.ddate DESC;
    ```
    
    User: "Net income of Tesla and Amazon"
    SQL:
    ```sql
    SELECT s.name, n.value, n.ddate FROM numbers n JOIN submissions s ON n.adsh = s.adsh WHERE (UPPER(s.name) LIKE 'TESLA%' OR UPPER(s.name) LIKE 'AMAZON%') AND n.tag = 'NetIncomeLoss' AND n.uom = 'USD' ORDER BY n.ddate DESC;
    ```
    
    Question: {question}
    """
    
    import re
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
            
        from backend.d_log import dlog
        dlog(f"Generated SQL: {sql_query}")
        
        # Execute SQL
        query_result = execute_sql_query(sql_query)
        # Safety: Final truncation if string is still massive
        if len(query_result) > 15000:
            query_result = query_result[:12000] + "\n...(Truncated for token limits)"
            
        dlog(f"DB Result Sample: {query_result[:200]}...")
        
        # KEY CHANGE: Handle Empty Data Explicitly
        if not query_result or "[]" in query_result or query_result.strip() == "":
            dlog("NO DATA FOUND from SQL execution.")
            return f"SQL Query Used:\n{sql_query}\n\nNO_DATA_FOUND_SIGNAL"
            
        # KEY CHANGE: Return raw result directly with SQL query for debugging.
        # The Auditor will handle the synthesis.
        return f"SQL Query Used:\n{sql_query}\n\nDatabase Results:\n{query_result}"
        
    except Exception as e:
        from backend.d_log import dlog
        dlog(f"Chain-of-Tables Error: {e}")
        return f"Error in Chain-of-Tables: {e}"
