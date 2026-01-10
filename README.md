# Agent Orchestration

A multi-agent chat application built with Python, LangGraph, LangChain, FastAPI, React, and MongoDB Atlas.

## Architecture

```
React Frontend  →  FastAPI Backend  →  LangGraph (Agent Orchestration)
                          ↓                        ↓
                    MongoDB Atlas            LangChain → Claude (Anthropic)
```

**Agents:**
- **Research Agent**: Analyzes queries and gathers structured insights
- **Writer Agent**: Synthesizes research into coherent responses

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Anthropic API key

## Quick Start

### 1. Clone and Navigate

```bash
cd agent-orchestration
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 3. Configure API Keys

Edit `backend/.env` and add your keys:

```env
# Get from: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Get from: MongoDB Atlas → Connect → Connect your application
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### 4. Set Up Frontend

```bash
cd ../frontend

# Install dependencies
npm install
```

### 5. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### 6. Open the App

Visit: http://localhost:5173

## Verification Steps

### Check Backend Health

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "mongodb": "connected",
  "anthropic": "configured",
  "errors": []
}
```

### Test Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Python?"}'
```

## MongoDB Atlas Setup

1. Go to [MongoDB Atlas](https://cloud.mongodb.com)
2. Create a free cluster (M0 tier)
3. Create a database user with password
4. Add your IP to the IP Access List (or use 0.0.0.0/0 for development)
5. Click "Connect" → "Connect your application"
6. Copy the connection string and replace `<password>` with your password

## Project Structure

```
agent-orchestration/
├── backend/
│   ├── app/
│   │   ├── agents/        # LangGraph agent workflow
│   │   ├── api/           # FastAPI routes
│   │   ├── core/          # Configuration
│   │   ├── db/            # MongoDB models & connection
│   │   └── main.py        # Application entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   └── index.css      # Styles
│   └── package.json
├── claude.md              # AI coding agent guide
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message, get agent response |
| GET | `/api/conversations` | List all conversations |
| GET | `/api/conversations/{id}` | Get conversation with messages |
| DELETE | `/api/conversations/{id}` | Delete a conversation |
| GET | `/api/health` | Check system health |

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Make sure you copied `.env.example` to `.env`
- Verify your API key is correct (starts with `sk-ant-`)

### "MongoDB connection failed"
- Check your connection string format
- Ensure your IP is whitelisted in Atlas
- Verify the password doesn't have special characters that need URL encoding

### "Cannot connect to backend"
- Make sure the backend is running on port 8000
- Check for errors in the backend terminal

### CORS Errors
- The backend allows localhost:5173 and localhost:3000
- If using a different port, add it to `app/main.py` CORS origins

## Extending the Application

### Add a New Agent

Edit `backend/app/agents/graph.py`:

```python
def my_new_agent(state: AgentState) -> AgentState:
    llm = get_llm()
    # Your agent logic
    return {"my_output": result}

# In build_agent_graph():
workflow.add_node("my_agent", my_new_agent)
workflow.add_edge("research", "my_agent")  # After research
workflow.add_edge("my_agent", "writer")     # Before writer
```

### Add LangChain Tools

```python
from langchain_core.tools import tool

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    # Tool implementation
    return results
```

### Change the LLM Model

Edit `backend/app/agents/graph.py`:

```python
def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",  # or "claude-haiku-4-5-20251001" for lower cost
        api_key=settings.anthropic_api_key,
    )
```

## Development Commands

```bash
# Backend
cd backend
uvicorn app.main:app --reload          # Dev server with hot reload
uvicorn app.main:app --host 0.0.0.0    # Expose to network

# Frontend
cd frontend
npm run dev      # Dev server
npm run build    # Production build
npm run preview  # Preview production build
```

## License

MIT
