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
You are a precise SQL generation model. Your ONLY job is to write a valid SQLite query.

Schema: {schema}

===== AVAILABLE DATA SOURCES =====

1. `swf` - PRIMARY P&L TABLE (Weekly Financials)
   - Columns: yr, qtr, mo, wk, item, val
   - Items: 'Revenue', 'Net Income', 'Cost of Revenue', 'Gross Profit', 'Operating Income', etc.
   - Use for: Revenue, profit, cost, income statement queries

2. `stock_prices` - STOCK DATA TABLE (Daily Prices)
   - Columns: date, symbol, open, high, low, close, volume, yr, mo, day, daily_return
   - Use for: Stock price, volume, trading queries
   
3. `financial_targets` - BUDGET TABLE
   - Columns: yr, qtr, metric, target_value, source
   - Use for: Budget vs actual comparisons

4. `profitability_metrics` - VIEW (Quarterly Margins)
   - Columns: yr, qtr, gross_margin_pct, operating_margin_pct, net_margin_pct
   - Use for: Margin queries, efficiency analysis

5. `variance_analysis` - VIEW (Budget vs Actual)
   - Columns: yr, qtr, metric, actual_value, target_value, variance_pct, status
   - Use for: Variance questions, "are we on target?"

6. `growth_metrics` - VIEW (QoQ Growth)
   - Columns: yr, qtr, item, growth_rate_qoq, trend
   - Use for: Growth rate, trend analysis

===== QUERY ROUTING RULES =====

| Question Type | Use Table/View |
|---------------|----------------|
| Revenue, Net Income, Costs | `swf` |
| Operating expenses, tax expense | `swf` (item LIKE '%Expense%') |
| Stock price, close, open, volume | `stock_prices` |
| Stock volatility | `stock_metrics` (intraday_volatility_pct column) |
| Budget, target, on track | `variance_analysis` or `financial_targets` |
| Margin, gross margin, net margin | `profitability_metrics` |
| Growth rate, growing, declining | `growth_metrics` |

===== EXAMPLES =====

User: "Revenue for 2024"
```sql
SELECT yr, qtr, SUM(val) as revenue FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY yr, qtr ORDER BY qtr;
```

User: "Operating expenses for 2024"
```sql
SELECT yr, qtr, item, SUM(val) as expense FROM swf WHERE item LIKE '%Expense%' AND yr = 2024 GROUP BY yr, qtr, item;
```

User: "Stock volatility in 2020"
```sql
SELECT yr, AVG(intraday_volatility_pct) as avg_volatility FROM stock_metrics WHERE yr = 2020 GROUP BY yr;
```

User: "Best closing price in 2020"
```sql
SELECT MAX(close) as best_close, date FROM stock_prices WHERE yr = 2020;
```

User: "What is the gross margin for 2024?"
```sql
SELECT yr, qtr, gross_margin_pct FROM profitability_metrics WHERE yr = 2024;
```

User: "Are we on target for revenue?"
```sql
SELECT yr, qtr, metric, actual_value, target_value, variance_pct, status FROM variance_analysis WHERE metric = 'Revenue' ORDER BY yr DESC, qtr DESC LIMIT 4;
```

User: "Is net income growing?"
```sql
SELECT yr, qtr, growth_rate_qoq, trend FROM growth_metrics WHERE item = 'Net Income' ORDER BY yr DESC, qtr DESC LIMIT 8;
```

User: "Stock volume above 1 million in 2015"
```sql
SELECT date, volume, close FROM stock_prices WHERE yr = 2015 AND volume > 1000000;
```

===== OUTPUT RULES =====
- WRAP SQL IN: ```sql ... ```
- No explanations.
- Use appropriate table/view based on question type.

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
