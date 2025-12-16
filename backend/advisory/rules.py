"""
Advisory Rules Engine
=====================
Defines rules for generating financial recommendations.
Each rule has:
- condition: SQL/logic condition to check
- severity: 'positive', 'info', 'warning', 'critical'
- insight: What the data tells us
- recommendation: Actionable advice
"""

# ============================================
# PROFITABILITY RULES
# ============================================
PROFITABILITY_RULES = {
    "excellent_gross_margin": {
        "metric": "gross_margin_pct",
        "condition": "> 40",
        "severity": "positive",
        "insight": "Gross margin exceeds 40%, indicating excellent production efficiency and pricing power.",
        "recommendation": "Maintain current pricing strategy. Consider investing in capacity expansion."
    },
    "healthy_gross_margin": {
        "metric": "gross_margin_pct",
        "condition": "BETWEEN 25 AND 40",
        "severity": "info",
        "insight": "Gross margin is in the healthy range (25-40%).",
        "recommendation": "Focus on maintaining efficiency while exploring margin improvement opportunities."
    },
    "low_gross_margin": {
        "metric": "gross_margin_pct",
        "condition": "< 25",
        "severity": "warning",
        "insight": "Gross margin is below 25%, indicating high production costs relative to revenue.",
        "recommendation": "Review supplier contracts, optimize production processes, or consider price adjustments."
    },
    "strong_net_margin": {
        "metric": "net_margin_pct",
        "condition": "> 15",
        "severity": "positive",
        "insight": "Net profit margin exceeds 15%, indicating strong overall profitability.",
        "recommendation": "Consider reinvesting profits into growth or increasing shareholder returns."
    },
    "weak_net_margin": {
        "metric": "net_margin_pct",
        "condition": "< 5",
        "severity": "critical",
        "insight": "Net profit margin is below 5%, indicating thin profitability.",
        "recommendation": "Urgently review all cost categories. Prioritize expense reduction and revenue optimization."
    },
    "strong_operating_margin": {
        "metric": "operating_margin_pct",
        "condition": "> 20",
        "severity": "positive",
        "insight": "Operating margin exceeds 20%, showing efficient day-to-day operations.",
        "recommendation": "Operations are well-managed. Focus on scaling current model."
    },
}

# ============================================
# GROWTH RULES
# ============================================
GROWTH_RULES = {
    "strong_revenue_growth": {
        "metric": "revenue_growth_qoq",
        "condition": "> 10",
        "severity": "positive",
        "insight": "Revenue is growing more than 10% quarter-over-quarter.",
        "recommendation": "Strong growth trajectory. Ensure operational capacity can support continued expansion."
    },
    "declining_revenue": {
        "metric": "revenue_growth_qoq",
        "condition": "< -5",
        "severity": "critical",
        "insight": "Revenue declined more than 5% quarter-over-quarter.",
        "recommendation": "Investigate market conditions, customer churn, and competitive pressures. Review sales strategy."
    },
    "flat_revenue": {
        "metric": "revenue_growth_qoq",
        "condition": "BETWEEN -5 AND 5",
        "severity": "info",
        "insight": "Revenue is relatively flat quarter-over-quarter.",
        "recommendation": "Consider new growth initiatives, market expansion, or product innovation."
    },
    "accelerating_profit": {
        "metric": "net_income_growth_qoq",
        "condition": "> 15",
        "severity": "positive",
        "insight": "Net income is growing faster than 15% QoQ, outpacing revenue growth.",
        "recommendation": "Excellent profit leverage. Continue cost discipline while scaling."
    },
    "profit_decline": {
        "metric": "net_income_growth_qoq",
        "condition": "< -10",
        "severity": "warning",
        "insight": "Net income declined more than 10% QoQ.",
        "recommendation": "Analyze cost structure. Identify areas of expense growth and address them."
    },
}

# ============================================
# VARIANCE RULES (Budget vs Actual)
# ============================================
VARIANCE_RULES = {
    "revenue_below_target": {
        "metric": "revenue_variance_pct",
        "condition": "< -10",
        "severity": "warning",
        "insight": "Revenue is more than 10% below budget target.",
        "recommendation": "Accelerate sales initiatives. Review pipeline and conversion rates."
    },
    "revenue_on_track": {
        "metric": "revenue_variance_pct",
        "condition": "BETWEEN -5 AND 5",
        "severity": "positive",
        "insight": "Revenue is within 5% of budget target.",
        "recommendation": "On track. Continue current strategy and monitor monthly progress."
    },
    "revenue_exceeding_target": {
        "metric": "revenue_variance_pct",
        "condition": "> 10",
        "severity": "positive",
        "insight": "Revenue exceeds budget by more than 10%.",
        "recommendation": "Excellent performance. Consider revising targets upward for next period."
    },
    "costs_over_budget": {
        "metric": "cost_variance_pct",
        "condition": "> 10",
        "severity": "critical",
        "insight": "Costs are more than 10% over budget.",
        "recommendation": "Implement immediate cost controls. Review top 3 over-budget categories."
    },
    "costs_under_budget": {
        "metric": "cost_variance_pct",
        "condition": "< -5",
        "severity": "positive",
        "insight": "Costs are 5% or more under budget.",
        "recommendation": "Good cost management. Ensure quality is not being compromised."
    },
}

# ============================================
# STOCK PRICE RULES
# ============================================
STOCK_RULES = {
    "high_volatility": {
        "metric": "intraday_volatility_pct",
        "condition": "> 5",
        "severity": "warning",
        "insight": "Stock shows high intraday volatility (>5% swings).",
        "recommendation": "Market uncertainty is elevated. Monitor news and fundamentals closely."
    },
    "price_momentum_positive": {
        "metric": "daily_return_5d_avg",
        "condition": "> 2",
        "severity": "info",
        "insight": "Stock has positive momentum with 5-day average return above 2%.",
        "recommendation": "Positive trend. Consider position sizing based on risk tolerance."
    },
    "price_momentum_negative": {
        "metric": "daily_return_5d_avg",
        "condition": "< -2",
        "severity": "warning",
        "insight": "Stock has negative momentum with 5-day average return below -2%.",
        "recommendation": "Downward pressure. Evaluate if fundamentals support current price level."
    },
    "volume_spike": {
        "metric": "volume_vs_avg",
        "condition": "> 200",
        "severity": "info",
        "insight": "Trading volume is more than 2x average.",
        "recommendation": "Unusual activity detected. Check for news or events driving interest."
    },
}

# ============================================
# COMBINED RULES DICTIONARY
# ============================================
ADVISORY_RULES = {
    **PROFITABILITY_RULES,
    **GROWTH_RULES,
    **VARIANCE_RULES,
    **STOCK_RULES,
}

def get_rule_by_metric(metric_name: str) -> list:
    """Get all rules related to a specific metric."""
    return [
        (name, rule) for name, rule in ADVISORY_RULES.items()
        if rule.get('metric', '').lower() == metric_name.lower()
    ]

def get_rules_by_severity(severity: str) -> list:
    """Get all rules with a specific severity level."""
    return [
        (name, rule) for name, rule in ADVISORY_RULES.items()
        if rule.get('severity', '').lower() == severity.lower()
    ]

if __name__ == "__main__":
    print(f"Total Advisory Rules: {len(ADVISORY_RULES)}")
    print("\nRules by Category:")
    print(f"  - Profitability: {len(PROFITABILITY_RULES)}")
    print(f"  - Growth: {len(GROWTH_RULES)}")
    print(f"  - Variance: {len(VARIANCE_RULES)}")
    print(f"  - Stock: {len(STOCK_RULES)}")
