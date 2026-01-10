# Agent Negotiation Arena - Claude Code Guide

This document provides comprehensive guidance for AI coding agents working with this codebase. It covers architecture, development practices, debugging, testing, and extension patterns.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Running the Application](#running-the-application)
5. [Debugging Guide](#debugging-guide)
6. [Testing Strategies](#testing-strategies)
7. [Key Files Deep Dive](#key-files-deep-dive)
8. [Agent System](#agent-system)
9. [API Reference](#api-reference)
10. [Frontend Architecture](#frontend-architecture)
11. [Common Development Tasks](#common-development-tasks)
12. [Code Patterns & Conventions](#code-patterns--conventions)
13. [Extending the System](#extending-the-system)
14. [Dependencies](#dependencies)
15. [Troubleshooting](#troubleshooting)
16. [External References](#external-references)

---

## Project Overview

### Purpose
A multi-agent negotiation system demonstrating AI agents negotiating based on private information. Two agents (A and B) negotiate turn-by-turn while a Judge evaluates progress, detects deadlocks, and identifies consensus.

### Core Concept
- Each agent has **private information** invisible to the other agent
- Agents must reach a **shared goal** through negotiation
- A **Judge** monitors progress without access to private information
- System automatically terminates on **consensus** or **deadlock**

### Use Cases
- Price negotiations (buyer/seller)
- Salary negotiations (candidate/employer)
- Resource allocation (competing departments)
- Contract negotiations (parties with constraints)

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  React + Vite (port 5173)                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Goal Input  │  │ Agent A     │  │ Agent B                 │  │
│  │             │  │ Private Info│  │ Private Info            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Negotiation Transcript (SSE Stream)            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│  FastAPI + Uvicorn (port 8000)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ API Routes   │  │ Session      │  │ Agent Orchestration    │ │
│  │ /api/        │  │ Storage      │  │ (LangChain)            │ │
│  │ negotiate/*  │  │ (In-Memory)  │  │                        │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT SYSTEM                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   Agent A    │  │   Agent B    │  │        Judge           │ │
│  │ (Negotiator) │  │ (Negotiator) │  │   (Evaluator)          │ │
│  │              │  │              │  │                        │ │
│  │ - Goal       │  │ - Goal       │  │ - Goal (no private)    │ │
│  │ - Private A  │  │ - Private B  │  │ - Progress detection   │ │
│  │ - History    │  │ - History    │  │ - Deadlock detection   │ │
│  └──────────────┘  └──────────────┘  │ - Consensus detection  │ │
│                                      └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ANTHROPIC CLAUDE API                          │
│                    (claude-haiku-4-5-20251001)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
1. User fills form → Frontend
2. Frontend POSTs to /api/negotiate/stream
3. Backend creates session state
4. LOOP:
   a. Agent A generates response (LLM call)
   b. Agent B generates response (LLM call)
   c. Judge evaluates (LLM call)
   d. Backend streams turn data via SSE
   e. Frontend renders turn
   f. If consensus/deadlock → break
5. Final conclusion streamed
6. Frontend shows outcome
```

### Data Flow

```
NegotiationState flows through:
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Agent A  │ ──► │ Agent B  │ ──► │  Judge   │
│          │     │          │     │          │
│ Adds:    │     │ Adds:    │     │ Adds:    │
│ agent_a_ │     │ agent_b_ │     │ judge_   │
│ response │     │ response │     │ evaluation│
└──────────┘     └──────────┘     │ status   │
                                  │ history  │
                                  └──────────┘
```

---

## Project Structure

```
agent-orchestration/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry, CORS, lifespan
│   │   ├── agents/
│   │   │   ├── __init__.py      # Exports: run_negotiation_turn, run_full_negotiation
│   │   │   └── graph.py         # Agent A, Agent B, Judge implementations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py        # All API endpoints, session storage
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py        # Settings class, env var loading
│   │   └── db/
│   │       ├── __init__.py      # Model exports
│   │       └── models.py        # Pydantic request/response models
│   ├── venv/                    # Python virtual environment
│   ├── requirements.txt         # Python dependencies
│   ├── .env                     # Environment variables (gitignored)
│   └── .env.example             # Environment template
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main React component (all UI logic)
│   │   ├── main.jsx             # React entry point
│   │   └── index.css            # All styles (CSS variables, components)
│   ├── public/
│   ├── dist/                    # Production build output
│   ├── node_modules/
│   ├── index.html               # HTML entry
│   ├── package.json             # npm dependencies
│   ├── package-lock.json
│   └── vite.config.js           # Vite config with API proxy
├── SPECIFICATION.md             # Detailed system specification
├── README.md                    # User-facing documentation
└── CLAUDE.md                    # This file (AI agent guide)
```

---

## Running the Application

### Prerequisites
- Python 3.9+ (tested with 3.9, 3.11)
- Node.js 18+
- Anthropic API key

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

# Install dependencies (first time or after requirements.txt changes)
pip install -r requirements.txt

# Set up environment (first time only)
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies (first time or after package.json changes)
npm install

# Start development server
npm run dev
# Runs on http://localhost:5173

# Build for production
npm run build
# Output in dist/
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key (sk-ant-...) |
| `DEBUG` | No | `true` | Enable debug logging |
| `MAX_NEGOTIATION_TURNS` | No | `10` | Max turns before forced end |
| `DEADLOCK_THRESHOLD` | No | `3` | No-progress turns before deadlock |

### Verify Setup

```bash
# Check backend health
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","anthropic":"configured","errors":[]}

# Check API docs
open http://localhost:8000/docs
```

---

## Debugging Guide

### Backend Debugging

#### 1. Check Configuration First
```bash
curl http://localhost:8000/api/health | python3 -m json.tool
```

If `errors` array is not empty, fix configuration issues.

#### 2. Enable Debug Logging
In `.env`:
```
DEBUG=true
```

#### 3. Test Agent Workflow Directly
```python
# In Python REPL (with venv activated)
import asyncio
from app.agents import run_negotiation_turn

state = {
    "goal": "Test goal",
    "agent_a_info": "Test A info",
    "agent_b_info": "Test B info",
    "negotiation_history": [],
    "current_turn": 0,
    "status": "in_progress",
    "agent_a_response": "",
    "agent_b_response": "",
    "judge_evaluation": {},
    "final_conclusion": None,
    "progress_score": 0,
    "deadlock_counter": 0,
}

result = asyncio.run(run_negotiation_turn(state))
print(result["agent_a_response"])
print(result["agent_b_response"])
print(result["judge_evaluation"])
```

#### 4. Test API Endpoints Directly
```bash
# Test start endpoint
curl -X POST http://localhost:8000/api/negotiate/start \
  -H "Content-Type: application/json" \
  -d '{"goal": "Test", "agent_a_info": "A", "agent_b_info": "B"}'

# Test step endpoint (use session_id from above)
curl -X POST http://localhost:8000/api/negotiate/step \
  -H "Content-Type: application/json" \
  -d '{"session_id": "YOUR_SESSION_ID"}'
```

#### 5. Check LLM Responses
Add print statements in `graph.py`:
```python
def agent_a_node(state: NegotiationAgentState) -> dict:
    # ... existing code ...
    response = llm.invoke(messages)
    print(f"Agent A raw response: {response.content}")  # Debug
    return {"agent_a_response": response.content}
```

### Frontend Debugging

#### 1. Browser DevTools
- **Console**: Check for JavaScript errors
- **Network tab**: Inspect API requests/responses
- **Application tab**: Check local state

#### 2. Check API Connectivity
```javascript
// In browser console
fetch('/api/health').then(r => r.json()).then(console.log)
```

#### 3. SSE Stream Debugging
The `/api/negotiate/stream` endpoint uses Server-Sent Events. In Network tab, look for:
- Request type: `eventsource`
- Events coming in as `data: {...}`

#### 4. State Debugging
Add to App.jsx:
```javascript
useEffect(() => {
  console.log('Turns updated:', turns);
  console.log('Status:', status);
}, [turns, status]);
```

### Common Debug Scenarios

| Symptom | Debug Steps |
|---------|-------------|
| "Cannot connect to backend" | 1. Is uvicorn running? 2. Check port 8000 3. Check CORS in main.py |
| Agent returns empty response | 1. Check API key 2. Test LLM directly 3. Check prompt formatting |
| Judge always returns progress=true | 1. Check judge prompt 2. Verify JSON parsing in judge_node |
| Frontend not updating | 1. Check SSE stream in Network tab 2. Check React state updates |
| Negotiation never ends | 1. Check MAX_NEGOTIATION_TURNS 2. Verify judge is detecting consensus |

---

## Testing Strategies

### Manual API Testing

```bash
# 1. Health check
curl http://localhost:8000/api/health

# 2. Start session
curl -X POST http://localhost:8000/api/negotiate/start \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Agree on a fair price for a used car",
    "agent_a_info": "You are the buyer. Max budget: $15,000. You noticed scratches on the car.",
    "agent_b_info": "You are the seller. Minimum price: $12,000. You just did expensive maintenance."
  }'

# 3. Step through negotiation (use session_id from step 2)
curl -X POST http://localhost:8000/api/negotiate/step \
  -H "Content-Type: application/json" \
  -d '{"session_id": "YOUR_SESSION_ID"}'

# 4. Run full negotiation (one-shot)
curl -X POST http://localhost:8000/api/negotiate/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Agree on a fair price for a used car",
    "agent_a_info": "Buyer. Max: $15,000",
    "agent_b_info": "Seller. Min: $12,000"
  }'
```

### Unit Testing Pattern (Backend)

```python
# tests/test_agents.py
import pytest
from app.agents.graph import agent_a_node, agent_b_node, judge_node

@pytest.fixture
def sample_state():
    return {
        "goal": "Test goal",
        "agent_a_info": "Test A",
        "agent_b_info": "Test B",
        "negotiation_history": [],
        "current_turn": 0,
        "status": "in_progress",
        "agent_a_response": "",
        "agent_b_response": "",
        "judge_evaluation": {},
        "final_conclusion": None,
        "progress_score": 0,
        "deadlock_counter": 0,
    }

def test_agent_a_returns_response(sample_state):
    result = agent_a_node(sample_state)
    assert "agent_a_response" in result
    assert len(result["agent_a_response"]) > 0

# Run with: pytest tests/
```

### Integration Testing Pattern

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "unhealthy"]

def test_start_negotiation():
    response = client.post("/api/negotiate/start", json={
        "goal": "Test",
        "agent_a_info": "A",
        "agent_b_info": "B"
    })
    assert response.status_code == 200
    assert "session_id" in response.json()
```

### Frontend Testing Pattern

```javascript
// src/__tests__/App.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';

test('renders goal input', () => {
  render(<App />);
  expect(screen.getByLabelText(/negotiation goal/i)).toBeInTheDocument();
});

test('start button disabled when fields empty', () => {
  render(<App />);
  const button = screen.getByText(/start negotiation/i);
  expect(button).toBeDisabled();
});
```

---

## Key Files Deep Dive

### `backend/app/agents/graph.py`

**Purpose**: Core agent logic - defines all three agents and orchestration.

**Key Components**:

```python
# State that flows through the system
class NegotiationAgentState(TypedDict):
    goal: str                    # Shared goal
    agent_a_info: str            # Private to Agent A
    agent_b_info: str            # Private to Agent B
    negotiation_history: list    # Public conversation
    current_turn: int            # Turn counter
    status: str                  # "in_progress" | "deadlock" | "consensus"
    agent_a_response: str        # Latest A response
    agent_b_response: str        # Latest B response
    judge_evaluation: dict       # Latest judge assessment
    final_conclusion: str | None # Final outcome
    progress_score: int          # 0-10 progress indicator
    deadlock_counter: int        # Consecutive no-progress turns

# Agent A: Has goal + agent_a_info + history
def agent_a_node(state) -> dict:
    # Returns: {"agent_a_response": "..."}

# Agent B: Has goal + agent_b_info + history + A's response
def agent_b_node(state) -> dict:
    # Returns: {"agent_b_response": "..."}

# Judge: Has goal + history only (no private info)
def judge_node(state) -> dict:
    # Returns: {"judge_evaluation": {...}, "status": "...", ...}

# Run one turn
async def run_negotiation_turn(state) -> dict:
    # Calls A → B → Judge sequentially

# Run full negotiation
async def run_full_negotiation(goal, a_info, b_info) -> dict:
    # Loops until consensus/deadlock/max_turns
```

### `backend/app/api/routes.py`

**Purpose**: HTTP endpoints and session management.

**Key Components**:

```python
# In-memory session storage
_sessions: dict[str, dict] = {}

# Endpoints
POST /api/negotiate/start   # Create session → returns session_id
POST /api/negotiate/step    # Run one turn → returns turn data
POST /api/negotiate/run     # Run full negotiation → returns all turns
POST /api/negotiate/stream  # SSE stream → yields turn events
GET  /api/negotiate/status  # Get session state
GET  /api/health            # Health check
```

### `backend/app/db/models.py`

**Purpose**: Pydantic models for type safety and validation.

**Key Models**:

```python
# Core data structures
JudgeEvaluation     # progress, progress_score, is_deadlock, is_consensus, reasoning
NegotiationTurn     # turn_number, agent_a_response, agent_b_response, judge_evaluation
NegotiationState    # Complete session state

# API contracts
StartNegotiationRequest   # goal, agent_a_info, agent_b_info
StartNegotiationResponse  # session_id, status, message
StepNegotiationResponse   # turn data
RunFullNegotiationResponse # all turns + conclusion
```

### `frontend/src/App.jsx`

**Purpose**: Complete React UI in a single file.

**Key Components**:

```javascript
// State
const [goal, setGoal] = useState('')           // Goal input
const [agentAInfo, setAgentAInfo] = useState('') // Agent A private info
const [agentBInfo, setAgentBInfo] = useState('') // Agent B private info
const [turns, setTurns] = useState([])         // Negotiation transcript
const [status, setStatus] = useState(null)     // in_progress/consensus/deadlock
const [finalConclusion, setFinalConclusion] = useState(null)

// Main function
startNegotiation()  // POSTs to /stream, reads SSE events, updates state

// Components
App()       // Main layout: header, setup panel, transcript, outcome
TurnCard()  // Single turn: A response, B response, judge evaluation
```

---

## Agent System

### Information Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        AGENT A                               │
│  Can see:                                                    │
│  ✓ Goal                                                      │
│  ✓ agent_a_info (private)                                    │
│  ✓ negotiation_history (all past public statements)          │
│  ✗ agent_b_info (NEVER)                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        AGENT B                               │
│  Can see:                                                    │
│  ✓ Goal                                                      │
│  ✓ agent_b_info (private)                                    │
│  ✓ negotiation_history + Agent A's current response          │
│  ✗ agent_a_info (NEVER)                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        JUDGE                                 │
│  Can see:                                                    │
│  ✓ Goal                                                      │
│  ✓ negotiation_history + current turn                        │
│  ✗ agent_a_info (NEVER)                                      │
│  ✗ agent_b_info (NEVER)                                      │
└─────────────────────────────────────────────────────────────┘
```

### Judge Evaluation Logic

```python
# Judge returns JSON:
{
    "progress": bool,        # Are agents moving toward goal?
    "progress_score": int,   # 0-10, how close to agreement
    "is_deadlock": bool,     # Positions entrenched?
    "is_consensus": bool,    # Agreement reached?
    "reasoning": str,        # Explanation
    "consensus_summary": str # If consensus, the agreement details
}

# Deadlock triggers when:
# - is_deadlock = true from judge, OR
# - deadlock_counter >= DEADLOCK_THRESHOLD (default 3)

# Consensus triggers when:
# - is_consensus = true AND consensus_summary provided
```

### Agent Prompt Structure

```python
# Agent A/B system prompt structure:
"""
You are Agent [A/B] in a negotiation. Your objective is to work toward this goal:
"{goal}"

YOUR PRIVATE INFORMATION (ONLY YOU HAVE ACCESS TO THIS - DO NOT REVEAL DIRECTLY):
{private_info}

IMPORTANT GUIDELINES:
- Work toward reaching the shared goal
- Use your private information to guide strategy (don't reveal directly)
- Be strategic but collaborative
- Make concrete proposals
- If agreement reached, state it clearly

This is turn {N} of the negotiation.
"""

# Judge system prompt structure:
"""
You are an impartial Judge evaluating a negotiation.

THE NEGOTIATION GOAL: "{goal}"

IMPORTANT: You do NOT have access to either agent's private information.

Evaluate:
1. Progress toward goal? (true/false)
2. Progress score? (0-10)
3. Deadlock? (positions entrenched)
4. Consensus? (explicit agreement)

Respond with ONLY valid JSON:
{...}
"""
```

---

## API Reference

### POST /api/negotiate/start

Start a new negotiation session.

**Request**:
```json
{
  "goal": "Agree on a fair price for the car",
  "agent_a_info": "Buyer. Max budget: $15,000",
  "agent_b_info": "Seller. Min price: $12,000"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "in_progress",
  "message": "Negotiation session created. Use /negotiate/step to proceed."
}
```

### POST /api/negotiate/step

Execute one round of negotiation.

**Request**:
```json
{
  "session_id": "uuid"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "turn": 1,
  "agent_a_response": "I'd like to offer $11,000 for the car...",
  "agent_b_response": "Thank you for your interest. Given the maintenance...",
  "judge_evaluation": {
    "progress": true,
    "progress_score": 3,
    "is_deadlock": false,
    "is_consensus": false,
    "reasoning": "Both parties stated initial positions...",
    "consensus_summary": null
  },
  "status": "in_progress",
  "final_conclusion": null
}
```

### POST /api/negotiate/stream

Stream negotiation via Server-Sent Events.

**Request**: Same as `/start`

**Response**: SSE stream with events:
```
data: {"type": "turn", "turn": 1, "agent_a_response": "...", ...}
data: {"type": "turn", "turn": 2, ...}
data: {"type": "complete", "status": "consensus", "final_conclusion": "..."}
```

### POST /api/negotiate/run

Run full negotiation until completion (blocking).

**Request**: Same as `/start`

**Response**:
```json
{
  "session_id": "uuid",
  "goal": "...",
  "status": "consensus",
  "turns": [...],
  "final_conclusion": "Agreement: $13,000",
  "total_turns": 4
}
```

---

## Frontend Architecture

### Component Structure

```
App (root)
├── Header
│   ├── Title
│   ├── Status Badge (in_progress/consensus/deadlock)
│   └── Health Indicator
├── Error Banner (conditional)
├── Main Content
│   ├── Setup Panel
│   │   ├── Goal Input (textarea)
│   │   ├── Agents Split
│   │   │   ├── Agent A Panel (textarea)
│   │   │   └── Agent B Panel (textarea)
│   │   └── Action Buttons (Start/Reset)
│   ├── Transcript Section (conditional)
│   │   ├── TurnCard (multiple)
│   │   │   ├── Turn Header (number + progress bar)
│   │   │   ├── Agent A Message
│   │   │   ├── Agent B Message
│   │   │   └── Judge Section (expandable)
│   │   └── Loading Indicator (during negotiation)
│   └── Outcome Section (conditional)
└── Footer
```

### State Management

```javascript
// Input state (user-controlled)
goal, setGoal
agentAInfo, setAgentAInfo
agentBInfo, setAgentBInfo

// Negotiation state (API-controlled)
turns, setTurns          // Array of turn objects
status, setStatus        // "in_progress" | "consensus" | "deadlock"
finalConclusion, setFinalConclusion
currentTurn, setCurrentTurn

// UI state
isNegotiating, setIsNegotiating  // Loading state
error, setError                   // Error messages
health, setHealth                 // Backend health
```

### CSS Architecture

```css
/* CSS Variables in :root */
--bg-primary, --bg-secondary, --bg-tertiary  /* Backgrounds */
--text-primary, --text-secondary, --text-muted /* Text colors */
--agent-a, --agent-b, --judge                  /* Agent colors */
--consensus, --deadlock                        /* Status colors */
--border-color                                 /* Borders */

/* Component prefixes */
.app-*          /* App-level components */
.setup-*        /* Setup panel */
.agent-*        /* Agent panels */
.transcript-*   /* Transcript area */
.turn-*         /* Turn cards */
.judge-*        /* Judge sections */
.outcome-*      /* Final outcome */
```

---

## Common Development Tasks

### Change Agent Behavior

**File**: `backend/app/agents/graph.py`

```python
def agent_a_node(state: NegotiationAgentState) -> dict:
    # Modify system_prompt to change personality/strategy
    system_prompt = f"""You are Agent A in a negotiation...

    # Add custom instructions here:
    Additional guidelines:
    - Be more aggressive in negotiations
    - Always start with a low offer
    - Focus on finding win-win solutions
    """
```

### Add New Agent Type

```python
# In graph.py
def mediator_node(state: NegotiationAgentState) -> dict:
    """Optional mediator that suggests compromises."""
    llm = get_llm()
    system_prompt = """You are a mediator helping Agent A and B..."""
    # ... implementation
    return {"mediator_suggestion": response.content}

# Modify run_negotiation_turn to include mediator
async def run_negotiation_turn(state: dict) -> dict:
    # ... existing A, B, Judge calls
    mediator_result = mediator_node(full_state)
    full_state.update(mediator_result)
    return full_state
```

### Change Deadlock/Consensus Criteria

**File**: `backend/app/agents/graph.py` in `judge_node`:

```python
# Modify judge system prompt
system_prompt = f"""...
CONSENSUS CRITERIA:
- Both agents must say "I agree" or "Deal"
- Specific terms must be mentioned
- No conditions or caveats

DEADLOCK CRITERIA:
- Same number repeated 3 times
- Explicit "final offer" statements
..."""
```

### Add New API Endpoint

**File**: `backend/app/api/routes.py`

```python
from app.db.models import NewRequest, NewResponse  # Create models first

@router.post("/negotiate/analyze", response_model=NewResponse)
async def analyze_negotiation(request: NewRequest):
    """Analyze a completed negotiation."""
    # Implementation
    return NewResponse(...)
```

### Add Frontend Feature

**File**: `frontend/src/App.jsx`

```javascript
// 1. Add state
const [newFeature, setNewFeature] = useState(null)

// 2. Add UI in return statement
<div className="new-feature">
  {/* Your component */}
</div>

// 3. Add styles in index.css
.new-feature {
  /* Your styles */
}
```

### Change LLM Model

**File**: `backend/app/agents/graph.py`

```python
def get_llm():
    settings = get_settings()
    return ChatAnthropic(
        # Options:
        # model="claude-haiku-4-5-20251001"  # Fast, cheap
        # model="claude-sonnet-4-20250514"  # Balanced
        # model="claude-opus-4-20250514"    # Best quality
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        temperature=0.7,  # 0.0-1.0, higher = more creative
    )
```

---

## Code Patterns & Conventions

### Backend Patterns

```python
# 1. Async functions for I/O
async def my_endpoint():
    result = await some_async_operation()

# 2. Type hints everywhere
def process(state: NegotiationAgentState) -> dict:
    ...

# 3. Pydantic for validation
class MyRequest(BaseModel):
    field: str = Field(..., description="Required field")
    optional: int | None = None

# 4. Settings via dependency injection
settings = get_settings()

# 5. Error handling pattern
try:
    result = await operation()
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### Frontend Patterns

```javascript
// 1. Functional components with hooks
function MyComponent({ prop }) {
  const [state, setState] = useState(initial)
  useEffect(() => { /* side effects */ }, [deps])
  return <div>...</div>
}

// 2. Conditional rendering
{condition && <Component />}
{condition ? <A /> : <B />}

// 3. Event handlers
const handleClick = () => { /* handler */ }
<button onClick={handleClick}>

// 4. Controlled inputs
<input value={value} onChange={(e) => setValue(e.target.value)} />

// 5. API calls in useEffect or handlers
const fetchData = async () => {
  const res = await fetch('/api/...')
  const data = await res.json()
  setState(data)
}
```

---

## Extending the System

### Adding Persistence (Database)

```python
# 1. Add to requirements.txt:
# motor==3.7.0  # For MongoDB
# sqlalchemy==2.0.0  # For SQL databases

# 2. Create db connection in app/db/database.py
# 3. Update routes to save/load sessions
# 4. Add migration scripts if needed
```

### Adding Authentication

```python
# 1. Add to requirements.txt:
# python-jose==3.3.0
# passlib==1.7.4

# 2. Create auth middleware in app/core/auth.py
# 3. Add protected routes with dependencies
@router.post("/negotiate/start")
async def start(request: Request, user: User = Depends(get_current_user)):
    ...
```

### Adding WebSocket Support

```python
# In routes.py
from fastapi import WebSocket

@router.websocket("/negotiate/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        result = await process(data)
        await websocket.send_json(result)
```

### Adding Multiple Agent Types

```python
# 1. Create agent factory
def create_agent(agent_type: str, config: dict):
    agents = {
        "negotiator": NegotiatorAgent,
        "mediator": MediatorAgent,
        "analyst": AnalystAgent,
    }
    return agents[agent_type](config)

# 2. Configure via API
class NegotiationConfig(BaseModel):
    agents: list[AgentConfig]
    rules: RulesConfig
```

---

## Dependencies

### Backend (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.6 | Web framework |
| uvicorn[standard] | 0.34.0 | ASGI server |
| python-dotenv | 1.0.1 | Environment loading |
| pydantic | 2.10.4 | Data validation |
| pydantic-settings | 2.7.1 | Settings management |
| langchain | 0.3.14 | LLM framework |
| langchain-anthropic | 0.3.0 | Claude integration |
| langchain-community | 0.3.14 | Community tools |
| langgraph | 0.2.62 | Agent orchestration |
| httpx | 0.28.1 | HTTP client |

### Frontend (package.json)

| Package | Version | Purpose |
|---------|---------|---------|
| react | 18.3.1 | UI framework |
| react-dom | 18.3.1 | React DOM |
| vite | 6.0.7 | Build tool |
| @vitejs/plugin-react | 4.3.4 | React plugin |

---

## Troubleshooting

### Backend Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | venv not activated | Run `source venv/bin/activate` |
| `ANTHROPIC_API_KEY not set` | Missing .env | Copy .env.example, add key |
| `ValidationError: Extra inputs` | Old .env with MongoDB vars | Settings has `extra="ignore"` now |
| Import errors | Missing package | Run `pip install -r requirements.txt` |
| Port in use | Another process on 8000 | Kill process or use different port |

### Frontend Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `npm install` fails | Node version | Use Node 18+ |
| API calls fail | Backend not running | Start backend first |
| CORS errors | Origin not allowed | Check main.py CORS config |
| SSE not working | Proxy issue | Check vite.config.js proxy |

### Agent Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty responses | API key invalid | Verify ANTHROPIC_API_KEY |
| JSON parse errors | Judge format | Check judge prompt for JSON format |
| Never reaches consensus | Prompt issue | Adjust consensus criteria in judge prompt |
| Immediate deadlock | Too strict criteria | Increase DEADLOCK_THRESHOLD |

---

## External References

### Documentation Links

- **Anthropic Claude**: https://docs.anthropic.com/
- **LangChain**: https://python.langchain.com/docs/
- **LangChain-Anthropic**: https://python.langchain.com/docs/integrations/chat/anthropic/
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/
- **React**: https://react.dev/
- **Vite**: https://vitejs.dev/

### Related Files in This Project

- `SPECIFICATION.md` - Detailed system specification
- `README.md` - User-facing documentation
- `.env.example` - Environment configuration template

### Model Information

- **claude-haiku-4-5-20251001**: Fast, cost-effective, good for high-volume
- **claude-sonnet-4-20250514**: Balanced performance/cost
- **claude-opus-4-20250514**: Best quality, higher cost

Current configuration uses Haiku for fast iterations. Change in `graph.py:get_llm()`.
