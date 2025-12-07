from groq import Groq
import os
from .tools.sql_tools import execute_sql_query, get_table_schemas
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "qwen/qwen3-32b"

CHAIN_OF_TABLES_PROMPT = """
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

def run_chain_of_tables(question: str, model: str = MODEL) -> str:
    """
    Executes the Chain-of-Tables reasoning loop.
    Note: For this simplified implementation, we will do a single-turn "Think-and-Query" 
    or rely on the LLM to generate the SQL, we execute it, and then feed it back.
    """
    schema = get_table_schemas()
    
    # Step 1: Ask LLM to generate SQL
    sql_generation_prompt = f"""
    You are a specific SQL generation model (Qwen). Your ONLY job is to write a valid SQLite query.
    
    Schema:
    {schema}
    
    IMPORTANT RULES:
    1. **ONLY SELECT**: You are strictly forbidden from writing INSERT, UPDATE, DELETE, or DROP queries.
    2. **Currency**: Always filter `WHERE n.uom = 'USD'` when comparing values across companies.
    3. **Joins**: 
       - `numbers` (n) JOIN `submissions` (s) ON `n.adsh = s.adsh`.
    4. **Dates**:
       - `ddate` is INTEGER YYYYMMDD.
       - Use `BETWEEN` for ranges (e.g. `20230101` AND `20231231`).
    5. **Output Format**:
       - WRAP YOUR SQL IN MARKDOWN BLOCK: ```sql ... ```
       - No explanations.
       - No conversational text like "Here is the query".

    EXAMPLES:
    User: "Revenue of Apple"
    SQL: 
    ```sql
    SELECT s.name, n.value, n.ddate FROM numbers n JOIN submissions s ON n.adsh = s.adsh WHERE s.name LIKE '%Apple%' AND n.tag = 'Revenues' AND n.uom = 'USD' ORDER BY n.ddate DESC LIMIT 10;
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
            return "NO_DATA_FOUND_SIGNAL"
            
        # KEY CHANGE: Return raw result directly. DO NOT SYNTHESIZE HERE.
        # The Auditor will handle the synthesis.
        return f"Database Results:\n{query_result}"
        
    except Exception as e:
        from backend.d_log import dlog
        dlog(f"Chain-of-Tables Error: {e}")
        return f"Error in Chain-of-Tables: {e}"
