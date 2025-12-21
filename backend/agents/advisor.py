"""
Advisor Agent
=============
Generates financial recommendations based on data context and advisory rules.
This agent is called after data retrieval to provide actionable insights.
"""
from groq import Groq
import os
import sqlite3
import json
from dotenv import load_dotenv

load_dotenv()

from backend.advisory.rules import ADVISORY_RULES, PROFITABILITY_RULES, GROWTH_RULES, VARIANCE_RULES

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"
DB_PATH = 'data/db/financial_data.db'

# ============================================
# DATA EXTRACTION FUNCTIONS
# ============================================

def get_latest_profitability_metrics():
    """Get the most recent profitability metrics from swf_financials."""
    try:
        conn = sqlite3.connect(DB_PATH)
        # CHANGED: Query swf_financials directly
        result = conn.execute("""
            SELECT year, quarter, gross_margin, operating_margin, net_margin, revenue, cost_of_revenue
            FROM swf_financials
            ORDER BY year DESC, quarter DESC
            LIMIT 1
        """).fetchone()
        conn.close()
        
        if result:
            return {
                "yr": result[0],
                "qtr": result[1],
                "gross_margin_pct": result[2] * 100 if result[2] is not None else 0, # Convert decimal to %
                "operating_margin_pct": result[3] * 100 if result[3] is not None else 0,
                "net_margin_pct": result[4] * 100 if result[4] is not None else 0,
                "latest_revenue": result[5] if result[5] is not None else 0,
                "latest_cost": result[6] if result[6] is not None else 0
            }
        return None
    except Exception as e:
        print(f"Error getting profitability: {e}")
        return None


def generate_advisory(question: str, data_context: str = None, interaction_id: str = None) -> str:
    """
    Generates an advisory response using the latest financial metrics.
    """
    # 1. Get latest metrics
    metrics = get_latest_profitability_metrics()
    
    if metrics:
        metrics_summary = (
            f"Period: {metrics['yr']} Q{metrics['qtr']}\\n"
            f"Gross Margin: {metrics['gross_margin_pct']:.1f}%\\n"
            f"Operating Margin: {metrics['operating_margin_pct']:.1f}%\\n"
            f"Net Margin: {metrics['net_margin_pct']:.1f}%\\n"
            f"Latest Revenue: ${metrics.get('latest_revenue', 0)/1e9:.2f}B\\n"
            f"Latest Cost of Revenue: ${metrics.get('latest_cost', 0)/1e9:.2f}B"
        )
    else:
        metrics_summary = "No recent data available."
        
    # Append provided context if any
    if data_context:
        metrics_summary += f"\\n\\nADDITIONAL CONTEXT FROM AUDITOR:\\n{data_context}"

    # Build advisory prompt - PROFESSIONAL & CAUTIOUS
    advisory_prompt = f"""
You are a Smart Financial Advisor.

You provide cautious, high-level recommendations based on long-term financial signals.

CONTEXT:
- Data represents a market-level virtual entity
- Quarterly fundamentals (2012–2025)
- Suitable for trends, not precise forecasting

RULES:
- NEVER give exact forecasts.
- Use directional language (increase / decrease / stable).
- Acknowledge uncertainty.
- Focus on sustainability and risk.

RESPONSE STRUCTURE:
Assessment:
Recommendation:
Risks:
Next Steps:

User question: {question}
Data summary:
{metrics_summary}
"""
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": advisory_prompt}],
            model=MODEL,
            temperature=0.4,  # Slightly higher for more thoughtful responses
            max_tokens=600    # Allow longer, more nuanced responses
        )
        
        recommendation = response.choices[0].message.content
        print(f"[Advisor] Generated recommendation")
        return recommendation
        
    except Exception as e:
        print(f"[Advisor] Error: {e}")
        # Fallback to cautious response
        return """**Assessment:** Unable to fully analyze this question at the moment due to system limitations.

**Recommendation:** Before making this decision, please review recent quarterly financial data and consult with your finance team.

**Risk Considerations:** Any financial decision should consider current market conditions and company-specific factors not captured in historical data.

**Suggested Next Steps:** Request a detailed analysis of relevant metrics for the most recent 4-8 quarters."""


if __name__ == "__main__":
    # Test the advisor
    print("=" * 60)
    print("ADVISOR AGENT TEST")
    print("=" * 60)
    
    test_questions = [
        "What is the best way to raise our profit?",
        "How can we improve our margins?",
        "Are we on track with our budget?",
    ]
    
    for q in test_questions:
        print(f"\n--- Question: {q} ---")
        result = generate_advisory(q)
        print(result)
