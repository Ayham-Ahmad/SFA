# SFA System Architecture

## Overview

The Smart Financial Advisory (SFA) system uses a **Retrieval-Augmented Multi-Agent System (RAMAS)** architecture to process financial queries.

```
┌─────────────────────────────────────────────────────────────┐
│                        USER QUERY                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  INTENT CLASSIFICATION                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │CONVERSATIONAL│ │  ANALYTICAL  │ │      ADVISORY        │ │
│  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘ │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐
   │   LLM    │    │    RAMAS     │    │  ADVISOR AGENT   │
   │ Response │    │   Pipeline   │    │ (Rules + LLM)    │
   └──────────┘    └──────┬───────┘    └──────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │  PLANNER  │──▶│  WORKER   │──▶│  AUDITOR  │
   └───────────┘   └───────────┘   └───────────┘
```

## RAMAS Pipeline

### 1. Planner Agent
- **Purpose**: Decompose complex queries into actionable steps
- **Input**: User question
- **Output**: Numbered list of SQL or RAG steps
- **File**: `backend/agents/planner.py`

### 2. Worker Agent
- **Purpose**: Execute each step (SQL queries or RAG retrieval)
- **Input**: Step instruction from Planner
- **Output**: Raw data/results
- **File**: `backend/agents/worker.py`

### 3. Auditor Agent
- **Purpose**: Synthesize results into human-readable response
- **Input**: Question + Worker results
- **Output**: Formatted answer (text or graph)
- **File**: `backend/agents/auditor.py`

## Advisory Engine

### Rules-Based Recommendations
Located in `backend/advisory/rules.py`:

| Category | Rules | Examples |
|----------|-------|----------|
| Profitability | 6 | Low/high margins, efficiency |
| Growth | 5 | Revenue trends, income growth |
| Variance | 5 | Budget tracking, over/under spend |
| Stock | 4 | Price momentum, volatility |

### Advisor Agent
- Extracts current metrics from database views
- Evaluates metrics against rules
- Generates LLM-powered recommendations
- **File**: `backend/agents/advisor.py`

## Data Layer

### Primary Tables

```sql
-- P&L Data
swf (yr, qtr, mo, wk, item, val)

-- Stock Prices
stock_prices (date, symbol, open, high, low, close, volume)

-- Budget Targets
financial_targets (yr, qtr, metric, target_value, source)
```

### Derived Views

```sql
-- Profitability Metrics
profitability_metrics (yr, qtr, gross_margin_pct, operating_margin_pct, net_margin_pct)

-- Variance Analysis
variance_analysis (yr, qtr, metric, actual_value, target_value, variance_pct, status)

-- Growth Metrics
growth_metrics (yr, qtr, item, growth_rate_qoq, trend)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Main query endpoint |
| `/api/dashboard/metrics` | GET | Dashboard data |
| `/api/live-data/{ticker}` | GET | Live stock data |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI |
| Database | SQLite |
| LLM | Groq API (Llama 3.3) |
| Frontend | HTML, CSS, JavaScript |
| Charts | Plotly.js |

## File Structure

```
backend/
├── agents/
│   ├── planner.py      # Query decomposition
│   ├── worker.py       # Step execution
│   ├── auditor.py      # Response generation
│   └── advisor.py      # Advisory recommendations
├── advisory/
│   ├── __init__.py
│   └── rules.py        # 20 financial rules
├── tools/
│   ├── sql_tools.py    # Database utilities
│   └── rag_tools.py    # RAG retrieval
├── routing.py          # RAMAS orchestration
├── llm.py              # LLM functions
├── prompts.py          # Centralized prompts
└── config.py           # Configuration
```

## Query Routing Logic

```python
# Intent Classification
if "should we" or "how to improve" in query:
    → ADVISORY (Advisor Agent)
elif "hello" or "who are you" in query:
    → CONVERSATIONAL (Direct LLM)
else:
    → ANALYTICAL (RAMAS Pipeline)
```

## Graph Generation

The Auditor generates Plotly.js charts:

```json
{
  "data": [
    {"x": ["Q1", "Q2", "Q3", "Q4"], "y": [10, 12, 8, 14], "type": "bar"}
  ],
  "layout": {"title": "Quarterly Revenue"}
}
```

Supported chart types:
- Bar charts (comparisons)
- Line charts (trends)
- Candlestick (stock OHLC)
- Pie charts (breakdowns)
