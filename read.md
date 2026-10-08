# Enterprise AI Control Plane - Architecture & Setup Guide

## Overview

Enterprise AI Control Plane is a customer support assistant system that uses **Retrieval-Augmented Generation (RAG)**, **agentic workflows**, and **multi-tier memory** to provide accurate, role-aware responses to enterprise queries.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Frontend / API Consumer)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI GATEWAY (app/main.py)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Auth      │  │  Rate Limit │  │   Audit     │  │  CORS       │        │
│  │  (JWT)      │  │  (Redis)    │  │  Logging    │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
            │  /chat      │   │ /documents  │   │ /metrics    │
            │  Endpoint   │   │  Endpoint   │   │  Endpoint   │
            └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
                   │                 │                 │
                   ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AGENTIC WORKFLOW (app/orchestration/workflow.py)        │
│                                                                             │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────┐  │
│   │ Planner │───▶│ Workers │───▶│ Critic  │───▶│ Memory  │───▶│Respond │  │
│   │ Agent   │    │(FAQ/RAG/│    │ Agent   │    │ Agent   │    │        │  │
│   └─────────┘    │ Sum/Reas)│    └─────────┘    └─────────┘    └────────┘  │
│                  └─────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Pinecone  │ │  PostgreSQL │ │   Redis     │ │   Groq LLM  │
    │  (Vector DB)│ │  (Relational)│ │  (Cache)    │ │  (Models)   │
    └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Core Components

### 1. **Planner Agent** (`app/agents/planner.py`)
- Classifies queries: `FAQ`, `RAG`, `SUMMARIZE`, `REASON`, `UNKNOWN`
- Uses rule-based + LLM classification
- Selects appropriate tools and model tier

### 2. **Worker Agents**
- **FAQ Agent** (`app/agents/faq_agent.py`): Handles common questions
- **RAG Agent** (`app/agents/rag_agent.py`): Document retrieval + grounded answers
- **Summarizer Agent** (`app/agents/summarizer_agent.py`): Text summarization
- **Reasoning Agent** (`app/agents/reasoning_agent.py`): Complex analysis/escalation

### 3. **Critic Agent** (`app/agents/critic_agent.py`)
- Validates responses for accuracy, safety, and policy compliance
- Returns `is_valid` flag and suggestions

### 4. **Memory System**
- **STM** (`app/memory/stm.py`): Short-term conversation history (PostgreSQL)
- **LTM** (`app/memory/ltm.py`): Long-term facts/preferences (Pinecone)
- **Compression** (`app/memory/compression.py`): Context summarization

### 5. **RAG Pipeline**
- **Ingestion** (`app/rag/ingestion.py`): Document chunking, embedding, indexing
- **Retriever** (`app/rag/retriever.py`): Hybrid search (vector + BM25), re-ranking
- **Chunker** (`app/rag/chunker.py`): Document segmentation

### 6. **Gateway Services**
- **Auth** (`app/gateway/auth.py`): JWT/OAuth2 with role-based claims
- **Rate Limiter** (`app/gateway/rate_limiter.py`): Redis-backed token bucket
- **Audit** (`app/gateway/audit.py`): Comprehensive logging, PII detection, drift monitoring

---

## Data Models

### Database (PostgreSQL/SQLite)
- `User` - Authentication and roles
- `Document` - Uploaded documents metadata
- `ChatSession` - Conversation sessions
- `ChatTurn` - Individual messages
- `AuditLog` - Action audit trail

### Vector Stores (Pinecone)
- **RAG Index**: Document chunks with role-based namespaces
- **LTM Index**: User facts, preferences, decisions

### Namespaces (Role-Based Access)
```
RAG: role:support_engineer, role:mortgage_analyst, role:compliance_officer, role:product_owner, role:global
LTM: user:preferences, facts:decisions, conversations:extracted
```

---

## Setup & Local Development

### Prerequisites
- Python 3.11+
- Redis (for rate limiting)
- Groq API Key

### Quick Start

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env  # Or edit .env directly
```

### Environment Variables (`.env`)

```ini
# App
APP_NAME=Enterprise AI Customer Support Assistant
ENVIRONMENT=development

# Database (SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite:///./test.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Pinecone (uses mock for testing)
PINECONE_API_KEY=mock_pinecone_key
PINECONE_RAG_INDEX=mock-rag-index
PINECONE_LTM_INDEX=mock-ltm-index

# Groq LLM
GROQ_API_KEY=your_groq_api_key
GROQ_BASE_URL=https://api.groq.com
SMALL_MODEL=openai/gpt-oss-20b
MEDIUM_MODEL=qwen/qwen3.8-27b
LARGE_MODEL=openai/gpt-oss-120b

# Auth
JWT_SECRET_KEY=your_secret_key
DISABLE_AUTH=true  # Dev only - bypasses JWT

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific tests
pytest tests/test_basic.py -v
pytest tests/test_e2e_upload_chat.py -v
```

### Run Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## API Endpoints

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Process chat query |
| POST | `/api/v1/chat/session` | Create session (role as query param) |
| GET | `/api/v1/chat/session/{id}` | Get session with turns |
| POST | `/api/v1/chat/stream` | Stream response (SSE) |
| GET | `/api/v1/chat/history/{id}` | Get chat history |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload document (multipart) |
| GET | `/api/v1/documents` | List documents |
| GET | `/api/v1/documents/{id}` | Get document |
| DELETE | `/api/v1/documents/{id}` | Delete document |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

---

## Key Fixes Applied (2026-10-08)

### 1. **Groq Model Names Fixed**
- **Problem**: Original config used decommissioned models (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`)
- **Fix**: Updated to models available on provided API key:
  - `SMALL_MODEL=openai/gpt-oss-20b`
  - `MEDIUM_MODEL=qwen/qwen3.8-27b`
  - `LARGE_MODEL=openai/gpt-oss-120b`

### 2. **RAG Embedding Function Rewritten**
- **Problem**: Hash-based embeddings didn't preserve semantic similarity → RAG retrieval failed
- **Fix**: TF-based word embeddings in `app/config/llm_providers.py:156-191`
  - Builds vocabulary from all texts
  - Creates TF vectors normalized to unit length
  - Preserves word-overlap similarity for mock Pinecone

### 3. **Test Isolation Added**
- **Problem**: Mock Pinecone state persisted between tests → flaky e2e test
- **Fix**: `tests/conftest.py` with autouse fixtures resetting:
  - Mock Pinecone indexes
  - Global singletons (RAG engine, chat workflow, ingestor)

### 4. **Modern FastAPI Lifespan**
- **Problem**: Deprecated `@app.on_event("startup")` pattern
- **Fix**: `lifespan` context manager in `app/main.py`

### 5. **Timezone-Aware Datetimes**
- **Problem**: `datetime.utcnow()` deprecated in Python 3.12+
- **Fix**: `datetime.now(timezone.utc)` across 6 files

### 6. **PDF Library Migration**
- **Problem**: `PyPDF2` deprecated
- **Fix**: `pypdf>=4.0.0` in requirements and `documents.py`

### 7. **Pinecone Namespace Handling**
- **Problem**: Mock didn't respect namespaces in upsert/query
- **Fix**: Namespace-prefixed keys in `MockPineconeIndex`

### 8. **Chat Session API Fix**
- **Problem**: Test sent role in JSON body, API expects query parameter
- **Fix**: Updated `test_e2e_upload_chat.py` to use `params={"role": ...}`

---

## Testing Strategy

### Test Files
| File | Purpose |
|------|---------|
| `test_basic.py` | Unit tests: settings, roles, query types, model router, planner, PII, health, metrics |
| `test_e2e_upload_chat.py` | Integration test: upload → list → session → chat → verify RAG response |

### Running in CI
```bash
# Install
pip install -r requirements.txt

# Run with coverage
pytest tests/ --cov=app --cov-report=xml
```

---

## Deployment Notes

### Docker
```dockerfile
# Multi-stage build in Dockerfile
# Uses python:3.11-slim base
```

### Kubernetes
- `k8s/` contains deployment manifests
- Uses `Deployment`, `Service`, `ConfigMap`, `Secret`

### Production Checklist
- [ ] Set `DISABLE_AUTH=false`
- [ ] Use real Pinecone (not mock)
- [ ] Use PostgreSQL (not SQLite)
- [ ] Configure real Redis
- [ ] Set strong `JWT_SECRET_KEY`
- [ ] Configure proper CORS origins
- [ ] Enable TLS/SSL
- [ ] Set up monitoring (LangSmith, Prometheus)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Model not found" 404 | Check `.env` models match Groq API key availability |
| Empty RAG responses | Verify embeddings work; check Pinecone index has vectors |
| Tests flaky | Run with `pytest tests/ -p no:cacheprovider` or use conftest fixtures |
| Auth 401 errors | Ensure `DISABLE_AUTH=true` in dev, or valid JWT in prod |
| Rate limited | Check Redis connection; adjust `REQUESTS_PER_MINUTE_PER_USER` |

---

## File Structure

```
EnterpriseAIControlPlane_python/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API routers (chat, documents)
│   │   ├── agents/           # Agent implementations
│   │   ├── config/           # Settings, Pinecone, LLM providers
│   │   ├── gateway/          # Auth, rate limit, audit
│   │   ├── memory/           # STM, LTM, compression
│   │   ├── orchestration/    # LangGraph workflow
│   │   ├── rag/              # RAG pipeline (ingestion, retriever, chunker)
│   │   ├── models/           # Pydantic/SQLAlchemy models
│   │   └── main.py           # FastAPI app entry
│   ├── tests/
│   │   ├── conftest.py       # Test fixtures (NEW)
│   │   ├── test_basic.py
│   │   └── test_e2e_upload_chat.py
│   ├── requirements.txt
│   ├── .env
│   └── alembic/              # DB migrations
├── frontend/                 # React/Vite frontend
├── k8s/                      # Kubernetes manifests
└── read.md                   # This file
```

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [Groq API Documentation](https://console.groq.com/docs)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)