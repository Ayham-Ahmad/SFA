# Smart Financial Advisory (SFA) System

A production-ready **Retrieval-Augmented Multi-Agent System (RAMAS)** that provides intelligent financial analysis and advisory recommendations.

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Data Queries** | Query P&L statements, stock prices, and financial metrics |
| **Advisory Engine** | Get actionable recommendations based on 20+ financial rules |
| **Graph Generation** | Visualize trends with Plotly.js charts |
| **Multi-Source** | Unified access to 6 data tables/views |

## 📊 Data Sources

| Table/View | Type | Description |
|------------|------|-------------|
| `swf` | Table | Weekly P&L data (Revenue, Net Income, Costs) - 1934-2025 |
| `stock_prices` | Table | Daily stock prices (Open, Close, Volume) - 2007-2024 |
| `financial_targets` | Table | Budget/target values for variance analysis |
| `profitability_metrics` | View | Calculated margins (Gross, Operating, Net) |
| `variance_analysis` | View | Budget vs Actual comparisons |
| `growth_metrics` | View | Quarter-over-quarter growth rates |

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file:
```
GROQ_API_KEY=your_groq_api_key
```

### 3. Run the Application
```bash
python -m uvicorn api.main:app --reload
```

### 4. Access the UI
Open `http://localhost:8000` in your browser.

## 💡 Sample Queries

### Data Queries
- "What is the total revenue for 2024?"
- "Show me the best closing price in 2020"
- "What is the gross margin for Q4?"

### Advisory Queries
- "What is the best way to improve our profit?"
- "Should we reduce costs?"
- "How can we improve our margins?"

### Graph Requests
- "[GRAPH_REQ] Show me revenue trend for 2024"
- "[GRAPH_REQ] Stock price chart for 2020"

## 🏗️ Architecture

```
SFA_V5/
├── api/                    # FastAPI endpoints
│   └── main.py
├── backend/
│   ├── agents/            # RAMAS agents
│   │   ├── planner.py     # Query decomposition
│   │   ├── worker.py      # SQL/RAG execution
│   │   ├── auditor.py     # Response synthesis
│   │   └── advisor.py     # Advisory recommendations
│   ├── advisory/          # Advisory rules engine
│   │   └── rules.py       # 20 financial rules
│   ├── tools/             # Database tools
│   │   └── sql_tools.py
│   ├── routing.py         # RAMAS pipeline
│   └── llm.py             # LLM integration
├── data/
│   └── db/financial_data.db  # SQLite database
└── frontend/              # HTML/CSS/JS UI
```

## 📈 Test Results

| Category | Queries | Accuracy |
|----------|---------|----------|
| P&L | 5 | 100% |
| Stock | 5 | 100% |
| Metrics | 4 | 100% |
| Advisory | 4 | 100% |
| Non-Financial | 2 | 100% |
| **Total** | **20** | **100%** |

## 🔧 Configuration

| Setting | Location | Description |
|---------|----------|-------------|
| `TESTING` | `backend/config.py` | Toggle test/production prompts |
| `MODEL` | `backend/llm.py` | LLM model selection |
| `DB_PATH` | `backend/tools/sql_tools.py` | Database path |

## 📝 License

This project is part of an Industrial Final Year Project (IFYP).

## 👤 Author

Developed for academic demonstration purposes.
