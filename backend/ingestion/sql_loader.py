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

# CIK Lookup Table - Major companies with their SEC CIK numbers
# This ensures reliable entity resolution instead of fuzzy string matching
COMPANY_CIK_LOOKUP = {
    # Tech Giants (FAANG+)
    "APPLE": {"cik": "320193", "name": "APPLE INC"},
    "MICROSOFT": {"cik": "789019", "name": "MICROSOFT CORP"},
    "GOOGLE": {"cik": "1652044", "name": "ALPHABET INC"},
    "ALPHABET": {"cik": "1652044", "name": "ALPHABET INC"},
    "AMAZON": {"cik": "1018724", "name": "AMAZON COM INC"},
    "META": {"cik": "1326801", "name": "META PLATFORMS INC"},
    "FACEBOOK": {"cik": "1326801", "name": "META PLATFORMS INC"},
    "NETFLIX": {"cik": "1065280", "name": "NETFLIX INC"},
    "NVIDIA": {"cik": "1045810", "name": "NVIDIA CORP"},
    "TESLA": {"cik": "1318605", "name": "TESLA INC"},
    "INTEL": {"cik": "50863", "name": "INTEL CORP"},
    "AMD": {"cik": "2488", "name": "ADVANCED MICRO DEVICES INC"},
    "CISCO": {"cik": "858877", "name": "CISCO SYSTEMS INC"},
    "ORACLE": {"cik": "1341439", "name": "ORACLE CORP"},
    "SALESFORCE": {"cik": "1108524", "name": "SALESFORCE INC"},
    "ADOBE": {"cik": "796343", "name": "ADOBE INC"},
    
    # Finance
    "JPMORGAN": {"cik": "19617", "name": "JPMORGAN CHASE & CO"},
    "JP MORGAN": {"cik": "19617", "name": "JPMORGAN CHASE & CO"},
    "BANK OF AMERICA": {"cik": "70858", "name": "BANK OF AMERICA CORP"},
    "WELLS FARGO": {"cik": "72971", "name": "WELLS FARGO & CO"},
    "GOLDMAN SACHS": {"cik": "886982", "name": "GOLDMAN SACHS GROUP INC"},
    "MORGAN STANLEY": {"cik": "895421", "name": "MORGAN STANLEY"},
    "VISA": {"cik": "1403161", "name": "VISA INC"},
    "MASTERCARD": {"cik": "1141391", "name": "MASTERCARD INC"},
    "BERKSHIRE": {"cik": "1067983", "name": "BERKSHIRE HATHAWAY INC"},
    
    # Healthcare/Pharma
    "JOHNSON & JOHNSON": {"cik": "200406", "name": "JOHNSON & JOHNSON"},
    "UNITEDHEALTH": {"cik": "731766", "name": "UNITEDHEALTH GROUP INC"},
    "PFIZER": {"cik": "78003", "name": "PFIZER INC"},
    "ABBVIE": {"cik": "1551152", "name": "ABBVIE INC"},
    "ELI LILLY": {"cik": "59478", "name": "ELI LILLY & CO"},
    "MERCK": {"cik": "310158", "name": "MERCK & CO INC"},
    
    # Retail/Consumer
    "WALMART": {"cik": "104169", "name": "WALMART INC"},
    "COSTCO": {"cik": "909832", "name": "COSTCO WHOLESALE CORP"},
    "HOME DEPOT": {"cik": "354950", "name": "HOME DEPOT INC"},
    "MCDONALDS": {"cik": "63908", "name": "MCDONALDS CORP"},
    "NIKE": {"cik": "320187", "name": "NIKE INC"},
    "STARBUCKS": {"cik": "829224", "name": "STARBUCKS CORP"},
    "COCA-COLA": {"cik": "21344", "name": "COCA COLA CO"},
    "COCA COLA": {"cik": "21344", "name": "COCA COLA CO"},
    "PEPSI": {"cik": "77476", "name": "PEPSICO INC"},
    "PEPSICO": {"cik": "77476", "name": "PEPSICO INC"},
    "PROCTER": {"cik": "80424", "name": "PROCTER & GAMBLE CO"},
    "P&G": {"cik": "80424", "name": "PROCTER & GAMBLE CO"},
    
    # Energy
    "EXXON": {"cik": "34088", "name": "EXXON MOBIL CORP"},
    "CHEVRON": {"cik": "93410", "name": "CHEVRON CORP"},
    
    # Industrial
    "BOEING": {"cik": "12927", "name": "BOEING CO"},
    "CATERPILLAR": {"cik": "18230", "name": "CATERPILLAR INC"},
    "3M": {"cik": "66740", "name": "3M CO"},
    "HONEYWELL": {"cik": "773840", "name": "HONEYWELL INTERNATIONAL INC"},
    "GENERAL ELECTRIC": {"cik": "40545", "name": "GENERAL ELECTRIC CO"},
    "GE": {"cik": "40545", "name": "GENERAL ELECTRIC CO"},
    
    # Telecom/Media
    "AT&T": {"cik": "732717", "name": "AT&T INC"},
    "VERIZON": {"cik": "732712", "name": "VERIZON COMMUNICATIONS INC"},
    "DISNEY": {"cik": "1744489", "name": "WALT DISNEY CO"},
    "COMCAST": {"cik": "902739", "name": "COMCAST CORP"},
    
    # Healthcare Distribution
    "MCKESSON": {"cik": "927653", "name": "MCKESSON CORP"},
}

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
    Now uses the CIK lookup table for reliability.
    """
    # Use hardcoded company names from lookup table
    companies = [info["name"] for info in COMPANY_CIK_LOOKUP.values()]
    unique_companies = list(set(companies))[:15]  # Dedupe and limit
    return ", ".join([f"'{company}'" for company in unique_companies])

def resolve_company_name(user_input: str) -> dict:
    """
    Resolves a user-provided company name to its official SEC name and CIK.
    Returns {"name": str, "cik": str} or None if not found.
    """
    # Normalize input
    query = user_input.upper().strip()
    
    # Direct lookup
    if query in COMPANY_CIK_LOOKUP:
        return COMPANY_CIK_LOOKUP[query]
    
    # Partial match - check if query is contained in any key
    for key, info in COMPANY_CIK_LOOKUP.items():
        if query in key or key in query:
            return info
    
    return None

def get_company_mapping_for_prompt() -> str:
    """
    Returns a formatted mapping of common company aliases to their SEC names.
    Critical for LLM to generate correct SQL with proper company names.
    """
    lines = ["COMPANY NAME MAPPING (Use the SEC Name in SQL):"]
    seen = set()
    
    for alias, info in COMPANY_CIK_LOOKUP.items():
        sec_name = info["name"]
        if sec_name not in seen:
            lines.append(f"  - '{alias}' → '{sec_name}'")
            seen.add(sec_name)
            if len(seen) >= 20:  # Limit to keep prompt manageable
                break
    
    return "\n".join(lines)
