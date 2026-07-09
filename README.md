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
- **RAG-based Retrieval**: Document retrieval with hybrid search (now with proper embeddings)
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

### Frontend (.env)

```bash
VITE_API_URL=http://localhost:8000
```

## User Guide: Step-by-Step Instructions

### 1. Application Access

After starting the application:
- Open your browser to `http://localhost:3000`
- You will see the login screen (see **Figure 1: Login Page**)

![Figure 1: Login Page](docs/screenshots/login.png)
*Login page with email and password fields*

### 2. Authentication

1. Enter your email address in the "Email" field
2. Enter your password in the "Password" field
3. Click the "Sign In" button
4. Upon successful authentication, you will be redirected to the main chat interface

### 3. Main Interface Overview

After login, you'll see the main application interface consisting of:

#### Header Section
- Application title: "Enterprise AI Customer Support"
- Help & Sample Queries button (question mark icon)
- Refresh and History buttons
- User email display

#### Role Selector
- Located below the header
- Allows switching between different user roles:
  - Support Engineer (default)
  - Mortgage Analyst
  - Compliance Officer
  - Product Owner
- Your selection affects how the AI responds and what data it can access

#### Main Content Area (Split View)
- **Left Panel (Chat Interface)**: ~70% width
  - Message display area
  - Input box for typing messages
  - Send button (paper plane icon)
  - Attachment, microphone, and emoji buttons
  
- **Right Panel (Sidebar)**: ~30% width
  - **Top Section**: Metrics Panel showing token usage, costs, and system status
  - **Bottom Section**: Sample queries and FAQ accordions

![Figure 2: Main Interface](docs/screenshots/main-interface.png)
*Main application interface showing chat window, role selector, and metrics panel*

### 4. Using the Chat Interface

#### Sending Messages
1. Click in the message input box at the bottom of the chat window
2. Type your question or request
3. Press Enter or click the send button (→) to submit
4. The AI will process your request and display a response

#### Message Types
- **User Messages**: Appear on the right side with a user icon
- **Assistant Messages**: Appear on the left side with a bot icon
- Each message shows:
  - Timestamp
  - Model used (e.g., "llama-3.1-8b-instant")
  - Sources consulted (if applicable)
  - Token usage information

#### Sample Queries
The right panel includes pre-built example questions organized by category:
- **Frequently Asked Questions**: Basic questions like return policies, password reset
- **Summarization Tasks**: Requests to summarize documents or text
- **Complex Reasoning**: Multi-step problem solving scenarios
- **FAQ Accordion**: Expandable sections with detailed answers to common questions

To use a sample query:
1. Click on any button in the sample queries section
2. The question will automatically appear in the input box
3. Press Enter or click send to submit the question

### 5. Document Management

#### Accessing the Documents Page
1. Click on the "Documents" link in the navigation (if available) or navigate directly to `/documents`
2. You will see the document management interface (see **Figure 3: Documents Page**)

![Figure 3: Documents Page](docs/screenshots/documents.png)
*Document management interface showing upload controls and document list*

#### Uploading Documents
1. Click the "Upload Document" button
2. Select one or more files from your computer (supported formats: PDF, DOC, DOCX, TXT)
3. Optionally specify a title for the document
4. The system will:
   - Extract text from the document
   - Split content into chunks
   - Generate embeddings for semantic search
   - Store vectors in Pinecone with appropriate metadata
   - Make the document available for querying

#### Document Status Indicators
Each document in the list shows:
- **Title**: Document name
- **Status**: Processing, Processed, or Failed
- **Uploaded**: Timestamp
- **Actions**: Eye icon (preview), Trash icon (delete)

#### Managing Documents
- **Preview**: Click the eye icon to view document details
- **Delete**: Click the trash icon to remove a document from the system
- **Refresh**: The document list automatically updates after uploads/deletions

### 6. Understanding Responses

When the AI responds to your query, you'll see:

#### Response Components
1. **Main Answer**: The AI's response to your question
2. **Sources**: If the answer was derived from documents, you'll see:
   - Source titles displayed as chips below the response
   - Each source shows the document title and source file
3. **Model Information**: 
   - Indicates which LLM model was used (based on query complexity and role)
   - Shown as "Model: [model-name]" in the message footer
4. **Timing**: Timestamp of when the response was generated

#### Example Response Flow
1. User asks: "What is the warranty period for our products?"
2. System processes query:
   - Classifies as RAG-type question
   - Routes to appropriate model (typically medium for RAG)
   - Retrieves relevant document chunks from Pinecone
   - Generates answer based on retrieved context
3. Response displays:
   - Answer text with warranty information
   - Source chips showing which documents were referenced
   - Model used: "llama-3.1-70b-versatile"
   - Timestamp

### 7. Monitoring & Metrics

The right panel includes a **Metrics Section** that displays:

#### Token Usage
- **Total Tokens**: Sum of input and output tokens for the session
- **Input Tokens**: Tokens sent to the model (your queries + context)
- **Output Tokens**: Tokens received from the model (AI responses)
- Visual progress bar showing usage vs. role-based limit (8,000 tokens by default)

#### Cost Estimation
- **Estimated Cost**: Calculated based on current model pricing
- Updates in real-time as you interact with the system

#### System Status
- **Quality Status**: Green check (normal) or red warning (drift detected)
- **Current Model**: Shows which model is actively being used
- **Role-based Limit**: Displays your token limit based on selected role

### 8. Special Features

#### Streaming Responses
- For longer responses, you may see text appear word-by-word as it's generated
- This provides a more responsive user experience

#### Context Awareness
- The system maintains conversation context within a session
- Previous messages inform responses to new questions
- Context is managed through short-term memory (STM) with compression

#### Role-Based Adaptation
Switching roles changes:
- How the AI interprets and responds to questions
- What document collections it can access (via namespaces)
- The tone and terminology used in responses
- Available sample questions and FAQs

### 9. Session Management

#### Session Persistence
- Your chat session is saved in localStorage
- Refreshing the page will restore your current conversation
- Closing the browser tab ends the session (data is not persisted server-side)

#### Creating New Sessions
- The system automatically generates a new session ID on initial load
- To start completely fresh:
  1. Clear your browser's localStorage for the application
  2. Or manually delete the "current_session_id" item
  3. Reload the page

### 10. Troubleshooting

#### Common Issues

**No Response or Empty Answer**
- Check if documents have been uploaded and processed
- Verify that the query is relevant to available documentation
- Try rephrasing the question using different terminology
- Ensure you have the correct role selected for accessing relevant documents

**Document Upload Failures**
- Verify file format is supported (PDF, DOC, DOCX, TXT)
- Check file size (typically limited to 10MB)
- Ensure PDF contains extractable text (not just scanned images)
- Look for specific error messages in the upload interface

**Slow Response Times**
- Check your internet connection
- Monitor the metrics panel for high token usage
- Consider simplifying complex queries
- The system may be experiencing high load

**Authentication Issues**
- Verify your credentials are correct
- Ensure your account has been properly provisioned in the system
- Contact your administrator if you continue to experience login problems

### 11. Logging Out

To end your session:
1. Simply close the browser tab
2. Or manually clear the application data from localStorage
3. No explicit logout button is required as the system uses token-based authentication with short expiration

## API Endpoints Reference

For developers or advanced users wishing to interact programmatically:

### Authentication
- `POST /api/v1/auth/login` - Authenticate user
- `POST /api/v1/auth/refresh` - Refresh access token

### Chat
- `POST /api/v1/chat` - Send a message and get response
- `POST /api/v1/chat/session` - Create new chat session
- `GET /api/v1/chat/session/{id}` - Retrieve session history
- `GET /api/v1/chat/history/{session_id}` - Get chat history for session

### Documents
- `POST /api/v1/documents` - Upload a new document
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get specific document details
- `DELETE /api/v1/documents/{id}` - Delete a document

### Memory
- `GET /api/v1/memory/profile` - Get user profile and preferences
- `GET /api/v1/memory/search?q={query}` - Search long-term memory
- `DELETE /api/v1/memory/sessions/{id}` - Delete a session's memory

### Health Checks
- `GET /api/v1/health` - Overall system health
- `GET /api/v1/health/database` - Database connectivity
- `GET /api/v1/health/llm` - LLM provider status
- `GET /api/v1/health/pinecone` - Vector database status
- `GET /api/v1/health/embeddings` - Embedding generation health

## Development & Customization

### Extending Functionality
1. **Adding New Roles**: Modify `src/components/RoleSelector/RoleSelector.tsx` and update role definitions
2. **Custom Sample Queries**: Edit the sample query buttons in `src/pages/Home.tsx`
3. **Styling Changes**: Adjust colors and themes in `src/styles/theme.ts`
4. **New Features**: Follow the existing pattern of creating components, hooks, and pages

### Testing
```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests  
cd frontend
npm test
```

## Support

For technical assistance or feature requests:
- Check the application logs for error details
- Review audit trails in the database
- Contact your system administrator
- Refer to the troubleshooting section above

---

*Documentation last updated: July 2024*
*Version: 1.0.0*