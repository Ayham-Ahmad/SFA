# Smart Financial Advisory (SFA) System

An AI-powered financial assistant that uses a **LangChain ReAct Agent** to provide intelligent financial analysis, data queries, and advisory recommendations.

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Natural Language Queries** | Ask questions about financial data in plain English |
| **Structured Advisory** | 7-section investment guidance with risk controls |
| **Graph Generation** | Interactive Plotly.js visualizations |
| **Multi-Tenant** | Users connect their own SQLite/CSV databases |
| **Dataset Upload** | Upload `.db` or `.csv` files directly (for hosted deployment) |

## 🚀 Quick Start (Local)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file:
```
GROQ_API_KEY=your_groq_api_key
SECRET_KEY=your_jwt_secret_key
```

### 3. Run the Application
```bash
uvicorn api.main:app --reload
```

### 4. Access the UI
Open `http://localhost:8000` in your browser.

---

## ☁️ Deploy to Railway

### 1. Push to GitHub
```bash
git add .
git commit -m "Deploy to Railway"
git push origin main
```

### 2. Create Railway Project
1. Go to [railway.app](https://railway.app) → Sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select your repository

### 3. Add Environment Variables
In Railway dashboard → **Variables** tab:

| Variable | Value |
|----------|-------|
| `GROQ_API_KEY` | Your Groq API key |
| `SECRET_KEY` | Any random string for JWT |
| `ACCOUNTS_DATABASE_URL` | `sqlite:////app/data/db/users_accounts_data.db` |

### 4. Add Persistent Volume
1. Click **"+ New"** → **"Volume"**
2. Mount path: `/app/data`
3. This ensures uploaded datasets persist across restarts

---

## 🏗️ Architecture

```
SFA_V5/
├── api/                    # FastAPI endpoints
│   ├── main.py             # App entry point
│   ├── routes/             # API routers (auth, chat, database, upload)
│   └── auth_utils.py       # JWT authentication
├── backend/
│   ├── agents/             # LangChain ReAct agent
│   │   └── langchain_agent.py
│   ├── pipeline/           # Query processing
│   │   ├── routing.py      # Intent classification
│   │   └── graph_pipeline.py
│   ├── tools/              # Agent tools
│   │   ├── sql_tools.py    # Database queries
│   │   ├── calculator.py   # Arithmetic operations
│   │   └── advisory_tool.py # Structured investment guidance
│   ├── services/           # Business logic
│   │   └── tenant_manager.py
│   └── utils/              # Helpers
│       └── llm_client.py   # Groq API client
├── frontend/               # HTML/CSS/JS UI
│   ├── templates/
│   └── static/
├── railway.toml            # Railway deployment config
└── Procfile                # Start command
```

## 🔧 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.10+, FastAPI |
| LLM Framework | LangChain (ReAct Agent) |
| LLM Provider | Groq API (Llama 3.3-70B) |
| Database | SQLite (multi-tenant) |
| Authentication | JWT (OAuth2) |
| Frontend | HTML, CSS, JavaScript |
| Charts | Plotly.js |
| Hosting | Railway (with persistent volumes) |

## 👥 User Roles

| Role | Access |
|------|--------|
| Admin | User management (CRUD) |
| Manager | Chatbot, analytics, settings, database connection |

## 💡 Sample Queries

### Data Queries
- "What is the total revenue for 2024?"
- "Show me gross margin for Q3 2023"
- "Compare revenue between 2022 and 2024"

### Advisory Queries
- "What's the best investment strategy based on last 2 months data?"
- "Should we invest more given current market trends?"

### Graph Requests
- Click the graph button to visualize data
- "Plot quarterly revenue for 2024"

## 🛡️ Advisory Framework

The SFA uses a **structured 7-section advisory template** to ensure high-quality, data-grounded recommendations:

1. **Objective Clarification** - Restates user goal, clarifies controllable factors
2. **Data Summary** - Time window, trends, volatility observed
3. **Insight & Interpretation** - What the data implies
4. **Recommended Strategy** - One clear recommendation with justification
5. **Execution Guidance** - Concrete steps and review triggers
6. **Risks & Assumptions** - Explicit disclaimers and downside protection
7. **Confidence Note** - Reliability statement

## 📝 License

This project is part of an Industrial Final Year Project (IFYP).

## 👤 Author

Developed for academic demonstration purposes.
