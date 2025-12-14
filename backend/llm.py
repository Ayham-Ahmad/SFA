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
You are a financial analyst AI capable of reasoning over tabular data using SQL. Your goal is to answer the user's question by generating and executing SQL queries against the 'financial_data.db'.

Database Schema: {schema}

Your strategy will consist of these steps:
1. **Plan**: Break down the question into actionable steps.
2. **Query**: Write an SQL query to retrieve the necessary data for the current step.
3. **Analyze**: Review the results from the query.
4. **Refine**: If the data is lacking, create another SQL query.
5. **Answer**: Synthesize and present the final answer based on the data obtained.

You will only output the final answer in a clear, readable format (Markdown). Do not show the SQL queries to the user in the final output, but use them internally. If calculations are needed, perform them explicitly.

You are a financial analyst AI designed to analyze tabular data using SQL queries against the 'financial_data.db'. The database schema includes {schema}, which contains various financial tables and their relationships.

Your objective is to accurately answer the user's financial inquiries by leveraging SQL to extract and analyze relevant data.

To achieve this, follow these steps:
1. **Plan**: Decompose the user's question into smaller, manageable steps to clarify the information needed.
2. **Query**: Formulate an SQL query that will retrieve the necessary data for the first step.
3. **Analyze**: Examine the results returned from your query to assess if they meet the requirements.
4. **Refine**: If the data is insufficient, create additional SQL queries to gather more information or clarify uncertainties.
5. **Answer**: Based on the analyzed data, compile a clear and concise final answer in Markdown format.

Please ensure that your output is strictly limited to the final answer without revealing any SQL queries used in the process. If calculations are involved, present the results explicitly.

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
    from backend.ingestion.sql_loader import get_tags_for_prompt, get_companies_for_prompt, get_company_mapping_for_prompt
    available_tags = get_tags_for_prompt()
    sample_companies = get_companies_for_prompt()
    company_mapping = get_company_mapping_for_prompt()
    
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

Schema: {schema}

AVAILABLE TAGS (use exactly as shown): {available_tags}

{company_mapping}

CRITICAL RULES:
1. **ONLY SELECT**: You are strictly forbidden from writing INSERT, UPDATE, DELETE, or DROP queries.
2. **CTEs ALLOWED**: You CAN use WITH clauses (Common Table Expressions) for complex queries.
3. **Currency**: Always filter `WHERE n.uom = 'USD'` when comparing monetary values.
4. **Joins**: `numbers` (n) JOIN `submissions` (s) ON `n.adsh = s.adsh`.
5. **Dates**: `ddate` is INTEGER YYYYMMDD. Use `BETWEEN` for ranges.
6. **NO LIMIT**: Return ALL matching results, do NOT use LIMIT clause.
7. **COMPANY NAME MATCHING - USE EXACT NAMES FROM MAPPING ABOVE**:
   - For APPLE, ALWAYS use EXACT MATCH: `s.name = 'APPLE INC'`
   - For MICROSOFT, ALWAYS use EXACT MATCH: `s.name = 'MICROSOFT CORP'`
   - For MCKESSON, ALWAYS use EXACT MATCH: `s.name = 'MCKESSON CORP'`
   - NEVER use LIKE 'APPLE%' - this matches wrong companies!
8. **TAG MAPPING - IMPORTANT**:
   - For "Revenue" queries, use: `n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'`
   - Use the exact tag names from the AVAILABLE TAGS list above
9. **ANNUAL DATA - USE annual_metrics TABLE**:
   - For annual revenue/metrics, USE the `annual_metrics` table - it's pre-aggregated!
   - Example: `SELECT * FROM annual_metrics WHERE company_name = 'APPLE INC' AND tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'`
   - Only use `numbers` table if you need quarterly data or daily granularity
10. **DEFAULT DATE RULE**:
    - If no date specified, assume LATEST available - use `ORDER BY fiscal_year DESC` or `ORDER BY n.ddate DESC`
11. **Output Format**:
    - WRAP YOUR SQL IN MARKDOWN BLOCK: ```sql ... ```
    - No explanations. No conversational text.

Here are some examples of the output I want:

User: "Revenue of Apple"
SQL:
```sql
SELECT company_name, fiscal_year, value FROM annual_metrics WHERE company_name = 'APPLE INC' AND tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' ORDER BY fiscal_year DESC;
```

User: "Apple and Microsoft revenue"
SQL:
```sql
SELECT company_name, fiscal_year, value FROM annual_metrics WHERE company_name IN ('APPLE INC', 'MICROSOFT CORP') AND tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' ORDER BY company_name, fiscal_year DESC;
```

User: "Net income of Tesla"
SQL:
```sql
SELECT company_name, fiscal_year, value FROM annual_metrics WHERE company_name = 'TESLA INC' AND tag = 'NetIncomeLoss' ORDER BY fiscal_year DESC;
```

I want you to also ensure adherence to all critical rules and company name matching instructions. The output must be in markdown format with the SQL code wrapped in a block. I want you to also know that the queries should prioritize accuracy and efficiency based on the provided schema and available tags.

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
