# Agent Orchestration - AI Coding Guide

This document helps AI coding agents understand and work with this codebase.

## Architecture Overview

```
┌─────────────────┐     HTTP      ┌─────────────────┐
│  React Frontend │◄────────────►│  FastAPI Backend │
│  (Vite, port    │               │  (Uvicorn, port │
│   5173)         │               │   8000)         │
└─────────────────┘               └────────┬────────┘
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                    ┌─────────▼─────────┐    ┌─────────▼─────────┐
                    │    LangGraph      │    │   MongoDB Atlas   │
                    │ (Agent Workflow)  │    │ (Conversations,   │
                    │                   │    │  Messages)        │
                    └─────────┬─────────┘    └───────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │    LangChain      │
                    │  (LLM Interface)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Claude (Haiku)   │
                    └───────────────────┘
```

## Project Structure

```
agent-orchestration/
├── backend/
│   ├── app/
│   │   ├── agents/         # LangGraph workflow
│   │   │   ├── __init__.py
│   │   │   └── graph.py    # Multi-agent orchestration
│   │   ├── api/            # FastAPI routes
│   │   │   └── routes.py   # REST endpoints
│   │   ├── core/           # Configuration
│   │   │   └── config.py   # Environment settings
│   │   ├── db/             # Database layer
│   │   │   ├── models.py   # Pydantic schemas
│   │   │   └── mongodb.py  # MongoDB connection
│   │   └── main.py         # FastAPI app entry
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main React component
│   │   ├── main.jsx        # React entry point
│   │   └── index.css       # Styles
│   ├── package.json
│   └── vite.config.js
└── claude.md               # This file
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/app/agents/graph.py` | **Core agent logic** - LangGraph workflow definition |
| `backend/app/api/routes.py` | API endpoints for chat and conversations |
| `backend/app/core/config.py` | Environment variable handling |
| `backend/app/db/mongodb.py` | MongoDB connection and helpers |
| `frontend/src/App.jsx` | Complete React UI |

## Technology Documentation

- **Claude (Anthropic)**: https://docs.anthropic.com/
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **LangChain**: https://python.langchain.com/docs/
- **LangChain-Anthropic**: https://python.langchain.com/docs/integrations/chat/anthropic/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Motor (async MongoDB)**: https://motor.readthedocs.io/
- **React**: https://react.dev/
- **Vite**: https://vitejs.dev/

## Common Development Tasks

### Add a New Agent

1. Edit `backend/app/agents/graph.py`
2. Create agent function following the pattern:
```python
def my_agent(state: AgentState) -> AgentState:
    """Agent docstring explaining its role."""
    llm = get_llm()
    # Agent logic here
    return {
        "some_state_key": result,
        "agent_steps": state.get("agent_steps", []) + [{"agent": "my_agent", "output": result}]
    }
```
3. Add node and edge to `build_agent_graph()`:
```python
workflow.add_node("my_agent", my_agent)
workflow.add_edge("previous_node", "my_agent")
```

### Add a New API Endpoint

1. Edit `backend/app/api/routes.py`
2. Add route using FastAPI decorators:
```python
@router.get("/new-endpoint")
async def new_endpoint():
    return {"data": "value"}
```

### Add LangChain Tools

1. Create tool in `backend/app/agents/` or inline in graph.py:
```python
from langchain_core.tools import tool

@tool
def my_tool(query: str) -> str:
    """Tool description for the LLM."""
    return "result"
```
2. Bind to agent's LLM:
```python
llm_with_tools = llm.bind_tools([my_tool])
```

### Modify MongoDB Schema

1. Update Pydantic models in `backend/app/db/models.py`
2. MongoDB is schemaless, so no migrations needed
3. Update API routes if response structure changes

## Debugging Guidelines

### Backend Issues

1. **Check configuration**:
   ```bash
   curl http://localhost:8000/api/health
   ```

2. **View logs**: Backend prints errors to console when running with `uvicorn`

3. **Test agent directly**:
   ```python
   # In Python REPL
   from app.agents import run_agent_workflow
   import asyncio
   result = asyncio.run(run_agent_workflow("test query"))
   print(result)
   ```

4. **MongoDB connection**: Verify URI format matches Atlas connection string exactly

### Frontend Issues

1. **API proxy**: Vite proxies `/api` to backend (see `vite.config.js`)
2. **Network tab**: Check browser dev tools for request/response
3. **Console errors**: React errors appear in browser console

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ANTHROPIC_API_KEY not set` | Missing env var | Copy `.env.example` to `.env`, add key |
| `MongoDB connection failed` | Bad URI or network | Check Atlas URI, whitelist IP |
| `Cannot connect to backend` | Server not running | Run `uvicorn app.main:app` |
| `CORS error` | Origin not allowed | Check `app/main.py` CORS origins |

## Agent Workflow Patterns

### Current Flow (Sequential)
```
User Query → Research Agent → Writer Agent → Response
```

### Adding Conditional Logic
```python
def route_decision(state: AgentState) -> str:
    """Decide which agent to route to based on state."""
    if "technical" in state["user_query"].lower():
        return "technical_agent"
    return "general_agent"

# In build_agent_graph():
workflow.add_conditional_edges(
    "classifier",
    route_decision,
    {"technical_agent": "technical", "general_agent": "general"}
)
```

### Adding Parallel Agents
```python
# Agents can run in parallel if they don't depend on each other
from langgraph.graph import StateGraph

workflow.add_node("agent_a", agent_a)
workflow.add_node("agent_b", agent_b)
workflow.add_node("combiner", combiner)

# Both route to combiner (effectively parallel)
workflow.add_edge("start", "agent_a")
workflow.add_edge("start", "agent_b")
workflow.add_edge("agent_a", "combiner")
workflow.add_edge("agent_b", "combiner")
```

## State Management

### AgentState Fields
```python
class AgentState(TypedDict):
    messages: list          # Conversation history (auto-appended)
    user_query: str         # Original user question
    research: str           # Research agent output
    final_response: str     # Final response to user
    agent_steps: list       # Audit trail of agent actions
```

### Adding New State Fields
1. Add to `AgentState` TypedDict in `graph.py`
2. Initialize in `run_agent_workflow()`
3. Access in agents via `state["field_name"]`

## Testing

### Manual API Testing
```bash
# Health check
curl http://localhost:8000/api/health

# Send chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Python?"}'

# List conversations
curl http://localhost:8000/api/conversations
```

### Python Testing
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_chat():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/chat", json={"message": "Hello"})
    assert response.status_code == 200
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude LLM |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | No | Database name (default: `agent_orchestration`) |
| `DEBUG` | No | Enable debug mode (default: `true`) |

## Best Practices

1. **Keep agents focused**: Each agent should have one clear responsibility
2. **Log agent steps**: Always append to `agent_steps` for observability
3. **Handle errors gracefully**: Catch exceptions in agents, return meaningful state
4. **Use async**: All DB and LLM calls should be async for performance
5. **Type hints**: Use Pydantic models for request/response validation
