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
    """Get the most recent profitability metrics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        result = conn.execute("""
            SELECT yr, qtr, gross_margin_pct, operating_margin_pct, net_margin_pct
            FROM profitability_metrics
            ORDER BY yr DESC, qtr DESC
            LIMIT 1
        """).fetchone()
        conn.close()
        
        if result:
            return {
                "yr": result[0],
                "qtr": result[1],
                "gross_margin_pct": result[2],
                "operating_margin_pct": result[3],
                "net_margin_pct": result[4]
            }
        return None
    except Exception as e:
        print(f"Error getting profitability: {e}")
        return None

def get_latest_growth_metrics():
    """Get the most recent growth metrics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get revenue growth
        revenue = conn.execute("""
            SELECT yr, qtr, growth_rate_qoq, trend
            FROM growth_metrics
            WHERE item = 'Revenue'
            ORDER BY yr DESC, qtr DESC
            LIMIT 1
        """).fetchone()
        
        # Get net income growth
        net_income = conn.execute("""
            SELECT yr, qtr, growth_rate_qoq, trend
            FROM growth_metrics
            WHERE item = 'Net Income'
            ORDER BY yr DESC, qtr DESC
            LIMIT 1
        """).fetchone()
        
        conn.close()
        
        return {
            "revenue_growth_qoq": revenue[2] if revenue else None,
            "revenue_trend": revenue[3] if revenue else None,
            "net_income_growth_qoq": net_income[2] if net_income else None,
            "net_income_trend": net_income[3] if net_income else None
        }
    except Exception as e:
        print(f"Error getting growth: {e}")
        return None

def get_latest_variance():
    """Get the most recent variance analysis."""
    try:
        conn = sqlite3.connect(DB_PATH)
        results = conn.execute("""
            SELECT metric, variance_pct, status
            FROM variance_analysis
            WHERE yr = (SELECT MAX(yr) FROM variance_analysis)
              AND qtr = (SELECT MAX(qtr) FROM variance_analysis WHERE yr = (SELECT MAX(yr) FROM variance_analysis))
            ORDER BY ABS(variance_pct) DESC
            LIMIT 5
        """).fetchall()
        conn.close()
        
        return [{"metric": r[0], "variance_pct": r[1], "status": r[2]} for r in results]
    except Exception as e:
        print(f"Error getting variance: {e}")
        return []

# ============================================
# RULE MATCHING FUNCTIONS
# ============================================

def evaluate_profitability_rules(metrics: dict) -> list:
    """Evaluate profitability rules against current metrics."""
    findings = []
    
    if not metrics:
        return findings
    
    for rule_name, rule in PROFITABILITY_RULES.items():
        metric_value = metrics.get(rule['metric'])
        if metric_value is not None:
            condition = rule['condition']
            matched = False
            
            if condition.startswith('>'):
                threshold = float(condition[1:].strip())
                matched = metric_value > threshold
            elif condition.startswith('<'):
                threshold = float(condition[1:].strip())
                matched = metric_value < threshold
            elif 'BETWEEN' in condition:
                parts = condition.replace('BETWEEN', '').replace('AND', ',').split(',')
                low, high = float(parts[0].strip()), float(parts[1].strip())
                matched = low <= metric_value <= high
            
            if matched:
                findings.append({
                    "rule": rule_name,
                    "metric": rule['metric'],
                    "value": metric_value,
                    "severity": rule['severity'],
                    "insight": rule['insight'],
                    "recommendation": rule['recommendation']
                })
    
    return findings

def evaluate_growth_rules(metrics: dict) -> list:
    """Evaluate growth rules against current metrics."""
    findings = []
    
    if not metrics:
        return findings
    
    # Map our metrics to rule metrics
    rule_map = {
        "revenue_growth_qoq": metrics.get("revenue_growth_qoq"),
        "net_income_growth_qoq": metrics.get("net_income_growth_qoq")
    }
    
    for rule_name, rule in GROWTH_RULES.items():
        metric_name = rule['metric']
        
        # Match rule metric to our data
        if 'revenue' in metric_name.lower():
            metric_value = rule_map.get("revenue_growth_qoq")
        elif 'net_income' in metric_name.lower() or 'profit' in metric_name.lower():
            metric_value = rule_map.get("net_income_growth_qoq")
        else:
            continue
        
        if metric_value is not None:
            condition = rule['condition']
            matched = False
            
            if condition.startswith('>'):
                threshold = float(condition[1:].strip())
                matched = metric_value > threshold
            elif condition.startswith('<'):
                threshold = float(condition[1:].strip())
                matched = metric_value < threshold
            elif 'BETWEEN' in condition:
                parts = condition.replace('BETWEEN', '').replace('AND', ',').split(',')
                low, high = float(parts[0].strip()), float(parts[1].strip())
                matched = low <= metric_value <= high
            
            if matched:
                findings.append({
                    "rule": rule_name,
                    "metric": metric_name,
                    "value": metric_value,
                    "severity": rule['severity'],
                    "insight": rule['insight'],
                    "recommendation": rule['recommendation']
                })
    
    return findings

# ============================================
# ADVISOR AGENT MAIN FUNCTION
# ============================================

def generate_advisory(question: str, data_context: str = None) -> str:
    """
    Generate financial advisory based on question and data.
    
    Args:
        question: The user's advisory question
        data_context: Optional SQL results or context
        
    Returns:
        Advisory recommendation string
    """
    print(f"\n[Advisor] Generating advisory for: {question}")
    
    # Gather current metrics
    profitability = get_latest_profitability_metrics()
    growth = get_latest_growth_metrics()
    variance = get_latest_variance()
    
    # Evaluate rules
    findings = []
    findings.extend(evaluate_profitability_rules(profitability))
    findings.extend(evaluate_growth_rules(growth))
    
    # Build context for LLM
    metrics_summary = f"""
CURRENT FINANCIAL STATUS (Latest Quarter):
- Gross Margin: {profitability.get('gross_margin_pct', 'N/A')}%
- Operating Margin: {profitability.get('operating_margin_pct', 'N/A')}%
- Net Margin: {profitability.get('net_margin_pct', 'N/A')}%
- Revenue Growth (QoQ): {growth.get('revenue_growth_qoq', 'N/A')}%
- Net Income Growth (QoQ): {growth.get('net_income_growth_qoq', 'N/A')}%
"""
    
    # Add variance info
    if variance:
        metrics_summary += "\nBUDGET VARIANCE (Top Items):\n"
        for v in variance[:3]:
            metrics_summary += f"- {v['metric']}: {v['variance_pct']}% ({v['status']})\n"
    
    # Add findings
    findings_text = ""
    if findings:
        findings_text = "\nKEY FINDINGS:\n"
        for f in findings[:5]:  # Top 5 findings
            findings_text += f"- [{f['severity'].upper()}] {f['insight']}\n"
            findings_text += f"  → {f['recommendation']}\n"
    
    # Add data context if provided
    context_text = ""
    if data_context:
        context_text = f"\nADDITIONAL DATA:\n{data_context[:500]}"
    
    # Build advisory prompt - PROFESSIONAL & CAUTIOUS
    advisory_prompt = f"""
You are a Professional Financial Advisor providing cautious, well-reasoned recommendations.

USER QUESTION: {question}

AVAILABLE DATA (treat with appropriate skepticism):
{metrics_summary}

DATA CONTEXT:
- This data is from weekly synthetic financials spanning 1934-2025
- Short-term volatility should be interpreted carefully given weekly granularity
- Aggregated metrics may mask recent performance variations

===== HARD RULES FOR DATA ANOMALIES =====

CRITICAL: If you see ANY of these, the data is INVALID for precise calculations:
- Margins exceeding 100% (mathematically impossible) → State: "Data distortion detected, not economically meaningful"
- Growth rates exceeding 500% quarter-over-quarter → State: "Extreme values suggest aggregation artifacts"
- Revenue/income jumps of 10x+ between quarters → State: "Data quality issue, values not reliable for projections"

WHEN DATA IS ANOMALOUS:
❌ DO NOT give exact projections (e.g., "$575.33B projected")
✅ USE ranges instead ("expected decline of 15-25%")
✅ USE directional statements ("significant negative impact likely")
✅ EXPLICITLY SAY: "Exact calculations are unreliable; only directional guidance is appropriate"

Example of WRONG response:
"Projected net income would be $575.33B" ← TOO PRECISE for bad data

Example of CORRECT response:
"Given the data quality concerns, exact projections are unreliable. Directionally, a 20% revenue decline would likely reduce net income substantially, though the magnitude cannot be precisely calculated."

===== STANDARD ADVISORY RULES =====

1. NEVER give absolute answers - always frame with conditions and caveats.
2. ACKNOWLEDGE data limitations clearly and prominently.
3. CONSIDER RISKS: Cash flow impact, downside scenarios, sustainability.
4. INCLUDE DECISION TRIGGERS: "proceed if X metric stays above Y for Z periods"
5. BE CONCISE: Clear, direct sentences without repetition.

RESPONSE FORMAT:
**Assessment:** (Data quality issues first, then sufficiency - 1-2 sentences)
**Recommendation:** (Conditional advice - use ranges if data is anomalous)
**Risk Considerations:** (Key risks - be specific and brief)
**Next Steps:** (1-2 concrete actions)

Answer the question: "{question}"
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
