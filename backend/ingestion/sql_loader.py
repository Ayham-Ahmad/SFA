"""
SQL Loader - Provides database metadata to help LLM generate accurate SQL queries.
Loads available tags and company name samples from the financial database.
"""
from sqlalchemy import create_engine, text
import pandas as pd
from functools import lru_cache

DB_PATH = "data/db/financial_data.db"

# Priority tags - most commonly used financial metrics (verified to exist in database)
PRIORITY_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",  # This is the actual Revenue tag
    "Revenues",  # Keep as fallback
    "NetIncomeLoss", 
    "GrossProfit",
    "OperatingIncomeLoss",
    "Assets",
    "AssetsCurrent",
    "Liabilities",
    "LiabilitiesCurrent",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "ProfitLoss",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "OperatingExpenses",
    "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "LongTermDebt",
    "CommonStockSharesOutstanding",
    "RetainedEarningsAccumulatedDeficit"
]

@lru_cache(maxsize=1)
def get_available_tags() -> list:
    """
    Returns priority financial tags that exist in the database.
    Uses a curated list of important tags verified against the database.
    """
    try:
        engine = create_engine(f"sqlite:///{DB_PATH}")
        with engine.connect() as conn:
            # Verify which priority tags actually exist in the database
            placeholders = ", ".join([f"'{tag}'" for tag in PRIORITY_TAGS])
            query = f"SELECT DISTINCT tag FROM numbers WHERE tag IN ({placeholders}) ORDER BY tag"
            df = pd.read_sql(query, conn)
            existing_tags = df['tag'].tolist()
            
            # Return existing priority tags, or fallback to the full list
            return existing_tags if existing_tags else PRIORITY_TAGS
    except Exception as e:
        print(f"Error loading tags from database: {e}")
        return PRIORITY_TAGS

@lru_cache(maxsize=1)
def get_company_names_sample() -> list:
    """
    Returns a sample of major company names from the database.
    Helps the LLM understand the naming convention (e.g., 'APPLE INC', 'MICROSOFT CORP').
    """
    try:
        engine = create_engine(f"sqlite:///{DB_PATH}")
        with engine.connect() as conn:
            # Get a sample of well-known companies
            query = """
                SELECT DISTINCT name FROM submissions 
                WHERE UPPER(name) LIKE 'APPLE INC%'
                   OR UPPER(name) LIKE 'MICROSOFT%'
                   OR UPPER(name) LIKE 'GOOGLE%'
                   OR UPPER(name) LIKE 'AMAZON%'
                   OR UPPER(name) LIKE 'META%'
                   OR UPPER(name) LIKE 'NVIDIA%'
                   OR UPPER(name) LIKE 'TESLA%'
                LIMIT 20
            """
            df = pd.read_sql(query, conn)
            return df['name'].tolist()
    except Exception as e:
        # Fallback to common examples if database query fails
        return ["APPLE INC", "MICROSOFT CORP", "AMAZON COM INC", "TESLA INC"]

def get_tags_for_prompt() -> str:
    """
    Returns a formatted string of available tags for inclusion in LLM prompt.
    """
    tags = get_available_tags()
    return ", ".join([f"'{tag}'" for tag in tags])

def get_companies_for_prompt() -> str:
    """
    Returns a formatted string of sample company names for inclusion in LLM prompt.
    """
    companies = get_company_names_sample()
    return ", ".join([f"'{company}'" for company in companies[:10]])
