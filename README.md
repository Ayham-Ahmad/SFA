# Smart Financial Advisory (SFA)

## Overview
SFA is an AI-powered financial advisory system that combines **RAG (Retrieval-Augmented Generation)**, **Chain-of-Tables** reasoning, and a **Multi-Agent System (RAMAS)** to provide accurate financial insights from structured data.

## Features
- **Interactive Dashboard**: View key metrics (Assets, Revenue) and revenue trends.
- **AI Chatbot**: Ask complex financial questions (e.g., "What is the total revenue for Apple?").
- **Multi-Agent Pipeline**:
  - **Planner**: Breaks down questions.
  - **Worker**: Executes RAG and SQL queries.
  - **Auditor**: Verifies and formats answers.
- **Role-Based Access**:
  - **Admin**: User management.
  - **Manager**: Dashboard and Chat access.
- **Security**: JWT Authentication, Password Hashing, Audit Logging.

## Setup & Running

1. **Prerequisites**:
   - Python 3.10+
   - SQLite
   - Groq API Key (in `.env`)

2. **Installation**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Initialization**:
   ```bash
   python -m backend.init_db
   python -m backend.ingestion.embed_data
   python -m backend.create_admin
   ```

4. **Running the App**:
   ```bash
   uvicorn api.main:app --reload
   ```

5. **Access**:
   - **Login**: http://127.0.0.1:8000/login
   - **Credentials**:
     - Admin: `admin` / `admin123`
     - Manager: `manager` / `manager123`

## Architecture
- **Frontend**: HTML/CSS/JS (Vanilla) + Plotly.js
- **Backend**: FastAPI
- **Database**: SQLite (`financial_data.db`, `users_accounts_data.db`)
- **Vector Store**: ChromaDB
- **LLM**: Llama-3.3-70b (via Groq)
