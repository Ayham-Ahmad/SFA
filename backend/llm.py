from groq import Groq
import os
from .tools.sql_tools import execute_sql_query, get_table_schemas
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

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

def run_chain_of_tables(question: str) -> str:
    """
    Executes the Chain-of-Tables reasoning loop.
    Note: For this simplified implementation, we will do a single-turn "Think-and-Query" 
    or rely on the LLM to generate the SQL, we execute it, and then feed it back.
    """
    schema = get_table_schemas()
    
    # Step 1: Ask LLM to generate SQL
    sql_generation_prompt = f"""
    You are a SQL expert. Given the database schema below, write a valid SQLite query to answer the user's question.
    
    IMPORTANT RULES:
    1. **Currency Safety**: The 'numbers' table has a 'uom' (Unit of Measure) column. 
       - If comparing companies (ranking), you MUST filter `WHERE n.uom = 'USD'`. 
       - NEVER compare USD with VND, JPY, etc. without filtering.
       - ALWAYS select `n.uom` in your results to be sure.
    
    2. **Table Joining**:
       - 'numbers' contains financial values (tag, value, ddate).
       - 'submissions' contains company info (name, sic, country).
       - JOIN them on `adsh`: `FROM numbers n JOIN submissions s ON n.adsh = s.adsh`.
    
    3. **Date Handling**:
       - `ddate` is an INTEGER in YYYYMMDD format.
       - For "Year 2023", use `n.ddate BETWEEN 20230101 AND 20231231`.
       - For "January 2025", use `n.ddate BETWEEN 20250101 AND 20250131`.
    
    4. **Text Matching Strategy**:
       - Priority 1: Use specific patterns if sure (e.g. `s.name LIKE 'APPLE INC%'`, `s.name LIKE 'MICROSOFT CORP%'`).
       - Priority 2: If searching generally, use broader matches but filter out noise (e.g. `s.name LIKE '%Apple%' AND s.name NOT LIKE '%Pineapple%'`).
       - **FALLBACK**: If you are unsure of the exact name format, try to match multiple variations using OR.
    
    5. **Date & Data Strategy (CRITICAL)**:
       - **Try to get data**: If the user asks for a specific date (e.g. "Last January") and you doubt it exists or want to be safe, modify the query to get a range or the latest available data.
       - **Better to show something**: Instead of `WHERE ddate = 20240131`, use `WHERE ddate >= 20230101 ORDER BY ddate DESC LIMIT 5`. This ensures we don't return "No data" just because the specific day is missing.
       - **Aggregation**: If asking for "Net Income" for a year, you usually want the value where `qtrs=4` (Annual) or sum of quarters. If unsure, just select the raw rows with date and let the user decide.
       - **Common Tags**: `NetIncomeLoss` (Most common), `ProfitLoss` (Fallback). If `NetIncomeLoss` yields no results, OR it with `ProfitLoss` (`tag IN ('NetIncomeLoss', 'ProfitLoss')`).
    
    6. **Example**:
       - Question: "Top 5 companies by Net Income in 2024?"
       - Query: `SELECT s.name, n.value, n.uom, n.ddate FROM numbers n JOIN submissions s ON n.adsh = s.adsh WHERE n.tag = 'NetIncomeLoss' AND n.uom = 'USD' AND n.ddate BETWEEN 20240101 AND 20241231 ORDER BY n.value DESC LIMIT 5`
    
    Schema:
    {schema}
    
    Question: {question}
    
    Return ONLY the SQL query. Do not explain your reasoning. Do not include "Here is the query". Just the SQL code.
    """
    
    try:
        # Generate SQL
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": sql_generation_prompt}],
            model=MODEL,
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Robust Cleaning
        sql_query = content
        if "```" in content:
            # Extract content between triple backticks
            import re
            match = re.search(r"```(?:sql)?(.*?)```", content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
        elif "SELECT" in content.upper():
            # Fallback: if no blocks, find the first SELECT and take it from there
            # (This is risky if there's text before, but better than nothing)
            # A better way is to rely on the prompt, but let's just strip leading text if it doesn't look like a query
            idx = content.upper().find("SELECT")
            if idx != -1:
                sql_query = content[idx:]
            
        print(f"Generated SQL: {sql_query}")
        
        # Execute SQL
        query_result = execute_sql_query(sql_query)
        # Safety: Final truncation if string is still massive
        if len(query_result) > 15000:
            query_result = query_result[:12000] + "\n...(Truncated for token limits)"
            
        print(f"Query Result: {query_result[:500]}...") # Truncate for log
        
        # Step 2: Synthesize Answer
        synthesis_prompt = f"""
        User Question: {question}
        
        Data Retrieved from Database:
        {query_result}
        
        Instructions:
        1. **Be Concise**: Answer directly. No filler words.
        2. **Financial Terms**: 'NetIncomeLoss' and 'ProfitLoss' tags represent the **SAME** concept (Bottom Line). Do **NOT** subtract "Profit - Loss". It is a single value. Positive = Profit, Negative = Loss.
        3. **Formatting**: Format large numbers (e.g., $1.2B).
        4. **Graph Generation (IMPORTANT)**: 
           - If the User asks for a "Graph" or "Chart", you MUST append a JSON object at the very end of your response using the specific key `graph_data||`.
           - Structure: `graph_data||{{"data": [{{"x": ["Label1", "Label2"], "y": [10, 20], "type": "bar", "name": "SeriesName"}}], "layout": {{"title": "Graph Title"}}}}`
           - Example response: "Here is the data... graph_data||{{...}}"
        5. **No Hallucinations**: If empty, state "No data found".
        """
        
        final_response = client.chat.completions.create(
            messages=[{"role": "user", "content": synthesis_prompt}],
            model=MODEL,
            temperature=0
        )
        return final_response.choices[0].message.content
        
    except Exception as e:
        return f"Error in Chain-of-Tables: {e}"
