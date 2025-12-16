"""
Phase 3 Verification: Test advisory functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("PHASE 3 VERIFICATION")
print("=" * 60)

# Test 1: Rules loaded
print("\n--- Advisory Rules ---")
from backend.advisory.rules import ADVISORY_RULES
print(f"✅ Total rules loaded: {len(ADVISORY_RULES)}")

# Test 2: Advisor agent metrics extraction
print("\n--- Advisor Agent Data Extraction ---")
from backend.agents.advisor import (
    get_latest_profitability_metrics,
    get_latest_growth_metrics,
    get_latest_variance
)

profitability = get_latest_profitability_metrics()
if profitability:
    print(f"✅ Profitability: Gross={profitability.get('gross_margin_pct')}%, Net={profitability.get('net_margin_pct')}%")
else:
    print("❌ Failed to get profitability metrics")

growth = get_latest_growth_metrics()
if growth:
    print(f"✅ Growth: Revenue QoQ={growth.get('revenue_growth_qoq')}%, Trend={growth.get('revenue_trend')}")
else:
    print("❌ Failed to get growth metrics")

variance = get_latest_variance()
if variance:
    print(f"✅ Variance: {len(variance)} items loaded")
else:
    print("❌ Failed to get variance data")

# Test 3: Rule evaluation
print("\n--- Rule Evaluation ---")
from backend.agents.advisor import evaluate_profitability_rules, evaluate_growth_rules

findings = evaluate_profitability_rules(profitability)
print(f"✅ Profitability rules matched: {len(findings)}")
for f in findings[:2]:
    print(f"   - {f['rule']}: {f['severity']}")

findings = evaluate_growth_rules(growth)
print(f"✅ Growth rules matched: {len(findings)}")
for f in findings[:2]:
    print(f"   - {f['rule']}: {f['severity']}")

# Test 4: Intent detection
print("\n--- Intent Detection ---")
advisory_keywords = [
    "should we", "should i", "best way to", "how to improve", "how can we",
    "what to do", "recommend", "advice", "suggestion", "strategy",
    "raise profit", "increase revenue", "reduce cost", "improve margin"
]

test_queries = [
    ("What is the best way to raise our profit?", True),
    ("How can we improve our margins?", True),
    ("What is the revenue for 2024?", False),
    ("Show me net income trend", False),
    ("Should we reduce costs?", True),
]

for query, expected in test_queries:
    is_advisory = any(kw in query.lower() for kw in advisory_keywords)
    status = "✅" if is_advisory == expected else "❌"
    print(f"{status} '{query[:40]}...' → Advisory={is_advisory}")

# Test 5: Generate advisory (will call LLM)
print("\n--- Advisory Generation (LLM) ---")
from backend.agents.advisor import generate_advisory

try:
    response = generate_advisory("What is the best way to raise our profit?")
    if response and len(response) > 50:
        print(f"✅ Advisory generated ({len(response)} chars)")
        print(f"   Preview: {response[:150]}...")
    else:
        print("❌ Advisory generation returned empty/short response")
except Exception as e:
    print(f"❌ Advisory generation failed: {e}")

print("\n" + "=" * 60)
print("PHASE 3 VERIFICATION COMPLETE")
print("=" * 60)
