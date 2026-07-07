# Enterprise AI Customer Support Assistant

A production-grade Enterprise AI Customer Support Assistant with RAG, memory, and agentic orchestration.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌─────────────────┐  ┌─────────────────────────────────────┐  │
│  │ React Frontend  │  │ LangSmith Tracing & Evaluation      │  │
│  │ - Chat UI       │  │ - Request/Response Tracing          │  │
│  │ - Role Selector │  │ - Metrics Collection                │  │
│  │ - Metrics Panel │  │ - Drift Detection                   │  │
│  └─────────────────┘  └─────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API GATEWAY LAYER                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ FastAPI Gateway Service                                  │  │
│  │ - Authentication & RBAC                                   │  │
│  │ - Model Routing                                             │  │
│  │ - Rate Limiting                                             │  │
│  │ - Audit Logging                                             │  │
│  │ - Drift Detection                                             │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ LangGraph Agentic Workflow                               │  │
│  │ - Planner → FAQ/RAG/Summarize/Reason                       │  │
│  │ - Critic → Validation                                      │  │
│  │ - Memory → STM/LTM Updates                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Postgres   │  │ Pinecone   │  │ S3         │  │ Redis    │  │
│  │ (STM)      │  │ (LTM+RAG)  │  │ (Documents)│  │ (Cache)  │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **FAQ Answering**: Instant responses to common questions
- **RAG-based Retrieval**: Document retrieval with hybrid search
- **Summarization**: Compress long texts and conversations
- **Complex Reasoning**: Multi-step analysis for escalations
- **Role-based Context**: Different responses per role
- **Memory System**: STM (short-term) + LTM (long-term) memory
- **Cost Optimization**: Model routing and context compression
- **Drift Detection**: Real-time quality monitoring

## Roles

- **Support Engineer**: Customer support and troubleshooting
- **Mortgage Analyst**: Loan analysis and underwriting
- **Compliance Officer**: Regulatory compliance and audits
- **Product Owner**: Product strategy and requirements

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Pinecone account

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd EnterpriseAIControlPlane_python

# Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Start frontend
cd ../frontend
npm install
npm run dev
```

### Docker Deployment

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Environment Variables

### Backend (.env)

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

# Redis
REDIS_URL=redis://red-d836e2t7vvec73938sl0:6379

# Pinecone
PINECONE_API_KEY=pcsk_6Vtb2n_Hz4fzzdc9DSFvaKdGBrEwERN2f4Z1PAmmKMVVRfFcpsus7qdfpo8x9du9TcZmvm
PINECONE_ENVIRONMENT=us-west-2
PINECONE_RAG_INDEX=mortgageindex
PINECONE_LTM_INDEX=mortgageindex
PINECONE_HOST=https://mortgageindex-96hwyzx.svc.aped-4627-b74a.pinecone.io

# Groq API
GROQ_API_KEY=your_groq_api_key_here

# Security
JWT_SECRET_KEY=your_jwt_secret_key

# LangSmith (optional)
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING=true
```

### LangSmith Monitoring

Access your LangSmith dashboard at:
- https://smith.langchain.com

LangSmith provides:
- Request/Response tracing
- LLM call evaluation
- Performance metrics
- Error tracking
- Custom evaluations

### Frontend (.env)

```bash
VITE_API_URL=http://localhost:8000
```

## API Endpoints

### Chat

- `POST /api/v1/chat` - Send a message
- `POST /api/v1/chat/session` - Create a session
- `GET /api/v1/chat/session/{id}` - Get session history

### Documents

- `POST /api/v1/documents` - Upload a document
- `GET /api/v1/documents` - List documents
- `DELETE /api/v1/documents/{id}` - Delete a document

### Memory

- `GET /api/v1/memory/profile` - Get user profile
- `GET /api/v1/memory/search?q=...` - Search memory
- `DELETE /api/v1/memory/sessions/{id}` - Delete session

### Health

- `GET /api/v1/health` - Overall health check
- `GET /api/v1/health/database` - Database health
- `GET /api/v1/health/llm` - LLM provider health
- `GET /api/v1/health/pinecone` - Pinecone health

## Testing

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

## Monitoring

- **LangSmith**: Automatic tracing of all LLM calls
- **Prometheus**: Metrics endpoint at `/metrics`
- **Grafana**: Dashboard for visualization (requires setup)

## Security

- JWT-based authentication
- Role-based access control (RBAC)
- PII scanning and redaction
- Rate limiting
- Audit logging

## License

MIT License