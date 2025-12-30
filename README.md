# Smart Financial Advisory (SFA) System

An AI-powered financial assistant that uses a **LangChain ReAct Agent** to provide intelligent financial analysis, data queries, and advisory recommendations.

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Data Queries** | Natural language queries on financial data |
| **Advisory Engine** | Investment recommendations via LLM |
| **Graph Generation** | Interactive Plotly.js visualizations |
| **Multi-Tenant** | Users connect their own SQLite/CSV databases |

## 🚀 Quick Start

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

## 🏗️ Architecture

```
SFA_V5/
├── api/                    # FastAPI endpoints
│   ├── main.py             # App entry point
│   ├── routes/             # API routers
│   └── auth_utils.py       # JWT authentication
├── backend/
│   ├── agents/             # LangChain agent
│   │   └── langchain_agent.py
│   ├── pipeline/           # Query processing
│   │   ├── routing.py      # Intent classification
│   │   └── graph_pipeline.py
│   ├── tools/              # Agent tools
│   │   ├── sql_tools.py
│   │   ├── calculator.py
│   │   └── advisory_tool.py
│   ├── services/           # Business logic
│   │   └── tenant_manager.py
│   └── utils/              # Helpers
│       └── llm_client.py   # Groq API client
└── frontend/               # HTML/CSS/JS UI
    ├── templates/
    └── static/
```

## 🔧 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI v2.0 |
| LLM Framework | LangChain (ReAct Agent) |
| LLM Provider | Groq API (Llama 3.3-70B) |
| Database | SQLite (multi-tenant) |
| Authentication | JWT (OAuth2) |
| Frontend | HTML, CSS, JavaScript |
| Charts | Plotly.js |

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
- "Should we invest more in marketing?"
- "How can we improve our profit margins?"

### Graph Requests
- Click the graph button to visualize data
- "Plot quarterly revenue for 2024"

## 📝 License

This project is part of an Industrial Final Year Project (IFYP).

## 👤 Author

Developed for academic demonstration purposes.
