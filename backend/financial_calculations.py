"""
Financial Metric Calculations

PHASE 7 — Derived Metric Construction
Compute financial metrics using multiple calculation paths.

Each function:
- Returns the calculated value and calculation source
- Supports multiple calculation paths (primary and fallback)
- Returns None if calculation is not possible
"""
from typing import Optional, Tuple, Dict, Any


def calculate_gross_profit(
    revenue: Optional[float] = None,
    cost_of_revenue: Optional[float] = None,
    operating_income: Optional[float] = None,
    operating_expenses: Optional[float] = None
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate Gross Profit.
    
    Primary:   Gross Profit = Revenue - Cost of Revenue
    Fallback:  Gross Profit = Operating Income + Operating Expenses
    
    Returns: (value, calculation_source) or (None, None) if not calculable
    """
    # Primary method: Revenue - Cost of Revenue
    if revenue is not None and cost_of_revenue is not None:
        # Note: cost_of_revenue is typically stored as negative
        value = revenue + cost_of_revenue  # Cost is negative, so + = -
        return (value, "Revenue - Cost of Revenue")
    
    # Fallback method: Operating Income + Operating Expenses
    if operating_income is not None and operating_expenses is not None:
        # Operating Expenses is negative
        value = operating_income - operating_expenses  # Expenses is negative, so - = +
        return (value, "Operating Income + Operating Expenses")
    
    return (None, None)


def calculate_operating_income(
    gross_profit: Optional[float] = None,
    operating_expenses: Optional[float] = None,
    income_before_tax: Optional[float] = None,
    other_income_expense: Optional[float] = None
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate Operating Income.
    
    Primary:   Operating Income = Gross Profit - Operating Expenses
    Fallback:  Operating Income = Income Before Tax - Other Income/Expense
    
    Returns: (value, calculation_source) or (None, None) if not calculable
    """
    # Primary method
    if gross_profit is not None and operating_expenses is not None:
        value = gross_profit + operating_expenses  # Expenses is negative
        return (value, "Gross Profit - Operating Expenses")
    
    # Fallback method
    if income_before_tax is not None and other_income_expense is not None:
        value = income_before_tax - other_income_expense
        return (value, "Income Before Tax - Other Income/Expense")
    
    return (None, None)


def calculate_income_before_tax(
    operating_income: Optional[float] = None,
    other_income_expense: Optional[float] = None,
    net_income: Optional[float] = None,
    income_tax_expense: Optional[float] = None
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate Income Before Tax.
    
    Primary:   Income Before Tax = Operating Income + Other Income/Expense
    Fallback:  Income Before Tax = Net Income + Income Tax Expense
    
    Returns: (value, calculation_source) or (None, None) if not calculable
    """
    # Primary method
    if operating_income is not None and other_income_expense is not None:
        value = operating_income + other_income_expense
        return (value, "Operating Income + Other Income/Expense")
    
    # Fallback method
    if net_income is not None and income_tax_expense is not None:
        value = net_income + income_tax_expense  # Tax is negative
        return (value, "Net Income + Income Tax Expense")
    
    return (None, None)


def calculate_net_income(
    income_before_tax: Optional[float] = None,
    income_tax_expense: Optional[float] = None
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate Net Income.
    
    Primary:   Net Income = Income Before Tax - Income Tax Expense
    
    Returns: (value, calculation_source) or (None, None) if not calculable
    """
    if income_before_tax is not None and income_tax_expense is not None:
        value = income_before_tax + income_tax_expense  # Tax is negative
        return (value, "Income Before Tax - Income Tax Expense")
    
    return (None, None)


def calculate_cost_of_revenue(
    revenue: Optional[float] = None,
    gross_profit: Optional[float] = None
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate Cost of Revenue (reverse calculation).
    
    Primary:   Cost of Revenue = Revenue - Gross Profit (returns as negative)
    
    Returns: (value, calculation_source) or (None, None) if not calculable
    """
    if revenue is not None and gross_profit is not None:
        value = -(revenue - gross_profit)  # Cost is stored as negative
        return (value, "Revenue - Gross Profit")
    
    return (None, None)


def calculate_all_derived_metrics(data: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """
    Calculate all possible derived metrics from input data.
    
    Args:
        data: Dictionary with keys like 'Revenue', 'Cost_of_Revenue', etc.
    
    Returns:
        Dictionary with calculated metrics and their sources
    """
    results = {}
    
    # Calculate Gross Profit
    value, source = calculate_gross_profit(
        revenue=data.get('Revenue'),
        cost_of_revenue=data.get('Cost_of_Revenue'),
        operating_income=data.get('Operating_Income'),
        operating_expenses=data.get('Operating_Expenses')
    )
    if value is not None:
        results['Gross_Profit'] = {'value': value, 'source': source, 'derived': True}
    
    # Calculate Operating Income
    value, source = calculate_operating_income(
        gross_profit=data.get('Gross_Profit') or results.get('Gross_Profit', {}).get('value'),
        operating_expenses=data.get('Operating_Expenses'),
        income_before_tax=data.get('Income_Before_Tax'),
        other_income_expense=data.get('Other_Income_Expense')
    )
    if value is not None:
        results['Operating_Income'] = {'value': value, 'source': source, 'derived': True}
    
    # Calculate Income Before Tax
    value, source = calculate_income_before_tax(
        operating_income=data.get('Operating_Income') or results.get('Operating_Income', {}).get('value'),
        other_income_expense=data.get('Other_Income_Expense'),
        net_income=data.get('Net_Income'),
        income_tax_expense=data.get('Income_Tax_Expense')
    )
    if value is not None:
        results['Income_Before_Tax'] = {'value': value, 'source': source, 'derived': True}
    
    # Calculate Net Income
    value, source = calculate_net_income(
        income_before_tax=data.get('Income_Before_Tax') or results.get('Income_Before_Tax', {}).get('value'),
        income_tax_expense=data.get('Income_Tax_Expense')
    )
    if value is not None:
        results['Net_Income'] = {'value': value, 'source': source, 'derived': True}
    
    return results


# ============ Example Usage ============
if __name__ == "__main__":
    # Example 1: Calculate from Revenue and Cost
    print("Example 1: Calculate Gross Profit from Revenue and Cost")
    value, source = calculate_gross_profit(revenue=100000000, cost_of_revenue=-60000000)
    print(f"  Gross Profit: ${value:,.0f}")
    print(f"  Source: {source}")
    
    # Example 2: Calculate all from partial data
    print("\nExample 2: Calculate all from partial data")
    data = {
        'Revenue': 100000000,
        'Cost_of_Revenue': -60000000,
        'Operating_Expenses': -15000000,
        'Other_Income_Expense': 2000000,
        'Income_Tax_Expense': -5000000
    }
    results = calculate_all_derived_metrics(data)
    for metric, info in results.items():
        print(f"  {metric}: ${info['value']:,.0f} ({info['source']})")
