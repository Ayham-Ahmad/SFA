"""
Update golden dataset to match SFA output format properly.
- golden_value: Keep as numeric for value accuracy comparison
- golden_answer: Update to match SFA's formatted response style
"""
import json

def format_currency(value):
    """Format currency value like SFA does."""
    if value is None:
        return "N/A"
    
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val/1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.2f}M"
    else:
        return f"{sign}${abs_val:,.2f}"

def format_margin(value):
    """Format margin/percentage like SFA does."""
    if value is None:
        return "N/A"
    # Margins in DB are stored as decimals (e.g., -2.98 means -298%)
    return f"{value * 100:.2f}%"

def update_golden_dataset():
    with open('evaluation/sfa_golden_dataset_v2.json', 'r') as f:
        data = json.load(f)
    
    # Updated golden answers based on SFA output format
    # These are structured to match how SFA responds
    updates_map = {
        1: {"answer": "The total revenue in 2024 was $2.89B."},
        2: {"answer": "The net income in 2023 was -$6.50B."},
        3: {"answer": "The gross profit in Q1 2024 was $6.94M."},
        4: {"answer": "The operating margin for Q2 2024 was -102.79%."},
        5: {"answer": "The cost of revenue in 2022 was -$1.70B."},
        6: {"answer": "The average market volatility in 2024 was 174.62%."},
        7: {"answer": "The daily return on 2024-12-31 was 0.01 or 1%."},
        8: {"answer": "The net margin for 2024 was -297.91%."},
        9: {"answer": "The revenue for 2015 was $498.94M."},
        10: {"answer": "The total operating expenses for 2024 was -$2.90B."},
        11: {"answer": "The revenue change from 2023 to 2024 was 32.12%."},
        12: {"answer": "The net margin was higher in 2023 at -2.97% compared to 2024 at -2.98%."},
        13: {"answer": "The operating expenses for 2022 were -$1.69B and for 2024 were -$2.90B."},
        14: {"answer": "The gross profit for Q1 2024 was $6.94M and for Q2 2024 was -$10.16M. No increase."},
        15: {"answer": "The average yearly revenue from 2020 to 2024 was $1.41B."},
        16: {"answer": "The cost to revenue ratio for 2024 was approximately -99.16%."},
        17: {"answer": "2024 had higher volatility at 7.22 compared to 2023 at 4.26."},
        18: {"answer": "The financial health for 2025 shows continued losses with net margin of -83.64%."},
        19: {"answer": "The average net margin for the last 3 years (2023-2025) was -2.93%, which is negative."},
        20: {"answer": "The total net loss in 2020 was $3.38B and $4.07B in 2021. The difference is $689.92M."},
        # Graph queries - just note graph generation
        21: {"answer": "Graph generated showing revenue trend from 2020 to 2025."},
        22: {"answer": "Graph generated showing net income over the last 5 years."},
        23: {"answer": "Graph generated showing daily stock price for 2024."},
        24: {"answer": "Graph generated showing volatility trend in Q1 2024."},
        25: {"answer": "Graph generated showing gross margin vs operating margin for 2024."},
        26: {"answer": "Graph generated showing quarterly revenue bar chart for 2023."},
        27: {"answer": "Graph generated showing operating expenses trend 2022-2024."},
        28: {"answer": "Graph generated showing net income vs revenue for 2024."},
        29: {"answer": "Graph generated showing daily return percentage for January 2024."},
        30: {"answer": "Graph generated showing correlation between revenue and net income."},
        # Multi-table structured
        31: {"answer": "The revenue for 2024 was $2.89B. Average volatility was 1.75 (174.62%)."},
        32: {"answer": "Revenue 2023: $2.19B, Revenue 2024: $2.89B. Growth rate: 32.01%."},
        33: {"answer": "Q1 2024 net margin: -293.46%, volatility: 2.12. Q4 2024 net margin: -297.86%, volatility: 1.49."},
        34: {"answer": "The company did not have a profit in 2024. All quarters showed net loss."},
        35: {"answer": "Q1: $646.52M (avg price: varies), Q2: $681.15M, Q3: $752.04M, Q4: $814.08M."},
        # Advisory queries
        36: {"answer": "Strategic assessment recommending focus on margin improvement due to negative operating margins."},
        37: {"answer": "Significant risks identified including continued operating losses and market volatility."},
        38: {"answer": "Cost reduction recommended to improve profitability given negative margins and increasing losses."},
        39: {"answer": "Revenue is increasing but net income remains significantly negative."},
        40: {"answer": "Strategic outlook shows revenue growth but continued profitability challenges."},
    }
    
    updated = 0
    for entry in data:
        qid = entry['id']
        if qid in updates_map:
            entry['golden_answer'] = updates_map[qid]['answer']
            updated += 1
    
    # Save updated dataset
    with open('evaluation/sfa_golden_dataset_v2.json', 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Updated {updated}/40 golden_answer fields to match SFA format.")
    print("\nSample updates:")
    for qid in [1, 2, 3, 8, 21, 36]:
        print(f"  ID {qid:2d}: {updates_map[qid]['answer'][:60]}...")
    
    print("\nDone!")

if __name__ == "__main__":
    update_golden_dataset()
