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

1. THIS IS SYNTHETIC DATA - There are NO real company names in the database.
2. Do NOT query for specific companies like Apple, Microsoft, Amazon, etc.
3. If the user asks about a specific company, the data does NOT exist.
4. entity_id = 'SYNTH_CO_01' represents the single synthetic company.

===== AVAILABLE TABLES =====

TABLE: swf_financials (Primary Income Statement / P&L Data)
Identifiers:
- entity_id: TEXT ('SYNTH_CO_01')
- data_source: TEXT ('SEC_SYNTHETIC')
- swf_id: INTEGER (unique row ID)

Time Structure (Quarter-based, NOT Calendar):
- fiscal_year: INTEGER (2012-2025)
- fiscal_quarter: INTEGER (1-4)
- month_in_quarter: INTEGER (1-3, resets each quarter)
- week_in_quarter: INTEGER (1-4, resets each quarter)
- period_id: INTEGER (fiscal_year*10 + fiscal_quarter, e.g. 20241)
- period_seq: INTEGER (sequential ordering)

Core Financial Metrics:
- Revenue: REAL (positive)
- Cost_of_Revenue: REAL (negative)
- Gross_Profit: REAL (Revenue + Cost_of_Revenue)
- Operating_Expenses: REAL (negative)
- Operating_Income: REAL (Gross_Profit + Operating_Expenses)
- Other_Income___Expense: REAL
- Income_Before_Tax: REAL (Operating_Income + Other_Income___Expense)
- Income_Tax_Expense: REAL (negative)
- Net_Income: REAL (Income_Before_Tax + Income_Tax_Expense)

Derived Metrics:
- gross_margin: REAL (Gross_Profit / Revenue)
- operating_margin: REAL (Operating_Income / Revenue)
- net_margin: REAL (Net_Income / Revenue)
- profit_flag: INTEGER (1 = profit, 0 = loss)
- margin_validity_flag: TEXT ('VALID', 'WARNING', 'DISTORTED')

Control Columns:
- synthetic_flag: INTEGER (always 1)
- agent_safe_to_use: INTEGER

---

TABLE: market_daily_data (Daily Stock Trading Data)
Identifiers:
- market_id: INTEGER
- symbol: TEXT ('SYNTH_STOCK')
- exchange_series: TEXT ('EQ')

True Calendar Time:
- trade_date: TEXT (YYYY-MM-DD format)
- year: INTEGER (2012-2025)
- month: INTEGER (1-12)
- day: INTEGER (1-31)
- fiscal_quarter: INTEGER (1-4, derived from month)

Price Metrics:
- open_price, high_price, low_price, close_price, last_price, vwap: REAL

Market Activity:
- trade_volume: INTEGER
- turnover: REAL
- number_of_trades: REAL
- deliverable_volume: INTEGER
- pct_deliverable: REAL

Derived Metrics:
- daily_return_pct: REAL
- volatility_flag: TEXT ('HIGH', 'MEDIUM', 'LOW')
- daily_price_direction: TEXT ('BULLISH', 'BEARISH', 'NEUTRAL')
- rolling_volatility: REAL (5-day rolling std)

===== LINKING RULES (VERY IMPORTANT) =====

✅ ALLOWED: Link on fiscal_year + fiscal_quarter ONLY
swf_financials.fiscal_year = market_daily_data.year
swf_financials.fiscal_quarter = market_daily_data.fiscal_quarter

❌ FORBIDDEN: Never link on week, month, or day (they have different meanings)

===== FINANCIAL FORMULAS =====

Gross Profit = Revenue - Cost of Revenue
Operating Income = Gross Profit - Operating Expenses
Income Before Tax = Operating Income + Other Income/Expense
Net Income = Income Before Tax - Tax Expense

Gross Margin = Gross Profit / Revenue
Operating Margin = Operating Income / Revenue
Net Margin = Net Income / Revenue

===== SQL GENERATION RULES =====

1. For P&L data (revenue, income, costs, margins) → use swf_financials
2. For stock prices (open, close, high, low, volume) → use market_daily_data
3. Always include ORDER BY for time-series data
4. Filter by fiscal_year for P&L data: WHERE fiscal_year = YYYY
5. Filter by year for stock data: WHERE year = YYYY
6. Use SUM() or AVG() for aggregations

===== EXAMPLES =====

"Revenue for 2024" →
```sql
SELECT fiscal_year, fiscal_quarter, SUM(Revenue) as revenue 
FROM swf_financials 
WHERE fiscal_year = 2024 
GROUP BY fiscal_year, fiscal_quarter 
ORDER BY fiscal_quarter
```

"Stock closing price 2020" →
```sql
SELECT trade_date, close_price 
FROM market_daily_data 
WHERE year = 2020 
ORDER BY trade_date
```

"Gross margin 2024" →
```sql
SELECT fiscal_year, fiscal_quarter, AVG(gross_margin) as gross_margin
FROM swf_financials 
WHERE fiscal_year = 2024 
GROUP BY fiscal_year, fiscal_quarter 
ORDER BY fiscal_quarter
```

"Net income trend" →
```sql
SELECT fiscal_year, fiscal_quarter, SUM(Net_Income) as net_income
FROM swf_financials 
GROUP BY fiscal_year, fiscal_quarter 
ORDER BY fiscal_year, fiscal_quarter
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
