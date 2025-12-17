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
    # sample_companies = get_companies_for_prompt()
    # company_mapping = get_company_mapping_for_prompt()
    
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
        sql_generation_prompt = f"""You are a precise SQL generator for a financial database.

===== CRITICAL DATA RULES =====

1. THIS IS SYNTHETIC DATA - There are NO company names in the database.
2. Do NOT query for specific companies like Apple, Microsoft, Amazon, etc.
3. If the user asks about a specific company, the data does NOT exist.
4. The `swf` table contains aggregated synthetic P&L data, NOT company-specific data.

===== AVAILABLE TABLES =====

TABLE: swf (Primary P&L Data)
- Columns: yr, qtr, mo, wk, item, val
- Items: 'Revenue', 'Net Income', 'Cost of Revenue', 'Gross Profit', 'Operating Income', 'Operating Expenses', 'Income Tax Expense', 'Other Income / Expense', 'Income Before Tax'
- Use for: Revenue, profit, cost questions

TABLE: stock_prices (Daily Stock Data)  
- Columns: date, symbol, open, high, low, close, volume, yr, mo, day, daily_return
- Use for: Stock price, open, close, volume questions

TABLE: stock_metrics (Derived Stock Metrics)
- Columns: yr, mo, avg_close, max_high, min_low, total_volume, intraday_volatility_pct
- Use for: Volatility, monthly summaries

VIEW: profitability_metrics (Margins)
- Columns: yr, qtr, gross_margin_pct, operating_margin_pct, net_margin_pct
- Use for: Margin questions

VIEW: variance_analysis (Budget vs Actual)
- Columns: yr, qtr, metric, actual_value, target_value, variance_pct, status
- Use for: Budget, target questions

VIEW: growth_metrics (Growth Rates)
- Columns: yr, qtr, item, growth_rate_qoq, trend
- Use for: Growth rate questions

===== SQL GENERATION RULES =====

1. Match question to correct table based on keywords
2. For P&L items (revenue, income, costs) → use `swf` table
3. For stock prices (open, close, high, low) → use `stock_prices` table
4. For volatility → use `stock_metrics` table
5. For margins → use `profitability_metrics` view
6. For budgets/targets → use `variance_analysis` view
7. For growth → use `growth_metrics` view
8. Always include ORDER BY for time-series data
9. Use SUM() or AVG() for aggregations
10. Filter by year using `yr = YYYY`

===== EXAMPLES =====

"Revenue for 2024" →
```sql
SELECT yr, qtr, SUM(val) as revenue FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY yr, qtr ORDER BY qtr
```

"Open vs close price 2020" →
```sql
SELECT date, open, close FROM stock_prices WHERE yr = 2020 ORDER BY date
```

"Stock volatility in 2020" →
```sql
SELECT yr, mo, intraday_volatility_pct FROM stock_metrics WHERE yr = 2020 ORDER BY mo
```

"Gross margin 2024" →
```sql
SELECT yr, qtr, gross_margin_pct FROM profitability_metrics WHERE yr = 2024 ORDER BY qtr
```

===== OUTPUT FORMAT =====

```sql
YOUR_QUERY_HERE
```

No explanations. Only the SQL query wrapped in code blocks.

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
