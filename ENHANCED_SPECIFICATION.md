# Privacy-Preserving Multi-Agent Negotiation Framework
## Specification v4.1 — Simplified MVP

---

# Part 1: Overview

## Problem
When AI agents negotiate, they must share information to find deals—but sharing too much (like walk-away prices) destroys negotiating power. LLMs are bad at keeping secrets.

## Solution
**Physical separation:** Each agent runs on its own backend server. Agent A's private data *cannot* reach Agent B because it never leaves Agent A's server.

| Innovation | What It Does | Why It Matters |
|------------|--------------|----------------|
| **Physical Separation** | Each agent runs in its own isolated backend | Privacy through architecture, not prompts |
| **BATNA Calculator** | Computes walk-away value privately on agent's server | Never transmitted—agent won't accept bad deals |
| **Contextual Integrity Gateway** | Filters what each agent shares BEFORE sending | Blocking happens at source, not destination |
| **MongoDB Audit Trail** | Logs each agent's thinking privately | Verifiable decision-making without data leakage |

## Key Negotiation Concepts

### BATNA (Best Alternative to Negotiated Agreement)
Each agent privately calculates their walk-away point based on their constraints:
- **Startup example:** "If I can't raise at $10M+, I have a bridge loan offer at $8M" → BATNA = $8M
- **Investor example:** "If this deal falls through, I have 3 other startups in pipeline" → BATNA = $0 (no pressure)

The BATNA is calculated and stored only on the agent's own server. It's used to:
1. Validate proposals before accepting (never accept below BATNA)
2. Guide strategy (strong BATNA → more aggressive negotiation)
3. Detect when to walk away

### Contextual Integrity Gateway
Before any message leaves the agent's server, it passes through a filter that checks:
- **ALLOW:** Information appropriate to share (growth metrics, general interest)
- **BLOCK:** Sensitive information that would harm negotiating position (exact BATNA, desperation signals)
- **TRANSFORM:** Sensitive info rephrased safely ("limited runway" instead of "8 months until bankruptcy")

This is logged in the audit trail so you can see exactly what was filtered.

---

# Part 2: Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              ARCHITECTURE                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐              ┌─────────────────────┐            │
│  │ AGENT A BACKEND     │              │ AGENT B BACKEND     │            │
│  │ localhost:8001      │              │ localhost:8002      │            │
│  │                     │              │                     │            │
│  │ • Private info      │              │ • Private info      │            │
│  │ • Thinking steps    │              │ • Thinking steps    │            │
│  │ • Writes to         │              │ • Writes to         │            │
│  │   agent_a_audit     │              │   agent_b_audit     │            │
│  │                     │              │                     │            │
│  │ Returns: public     │              │ Returns: public     │            │
│  │ message only        │              │ message only        │            │
│  └──────────┬──────────┘              └──────────┬──────────┘            │
│             │                                    │                        │
│             └────────────┬───────────────────────┘                        │
│                          │                                                │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                      ARENA BACKEND                                 │   │
│  │                      localhost:8000                                │   │
│  │                                                                    │   │
│  │  • Creates session, orchestrates turns                            │   │
│  │  • Calls agent backends via HTTP                                  │   │
│  │  • Runs Judge (sees only public messages)                         │   │
│  │  • Writes to public_sessions collection                           │   │
│  │  • Streams updates via SSE                                        │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                          │                                                │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                        MONGODB                                     │   │
│  │                                                                    │   │
│  │  agent_a_audit    │  agent_b_audit    │  public_sessions          │   │
│  │  (A's thinking)   │  (B's thinking)   │  (public messages)        │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                     NEXT.JS FRONTEND                               │   │
│  │                     localhost:3000                                 │   │
│  │                                                                    │   │
│  │  /agent-a  →  Calls :8001, shows A's thinking                     │   │
│  │  /agent-b  →  Calls :8002, shows B's thinking                     │   │
│  │  /arena    →  Calls :8000, shows public conversation only         │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Privacy Note:** All services share the same MongoDB connection. Privacy is enforced by *code discipline* (each backend only reads/writes its designated collection), not database-level access control. For a production system, you'd use separate credentials per service.

---

# Part 3: Session Lifecycle

This is the complete flow from start to finish:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SESSION LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PHASE 1: SETUP                                                         │
│  ═══════════════                                                        │
│                                                                          │
│  1. User opens /arena tab                                               │
│     → Enters goal: "Negotiate Series A terms"                           │
│     → Clicks [Create Session]                                           │
│     → Arena backend creates session, returns session_id                 │
│     → Frontend displays: "Session: abc123 - Share with participants"    │
│                                                                          │
│  2. User opens /agent-a tab (or shares link with Party A)               │
│     → Enters session_id: abc123                                         │
│     → Enters private info in textarea                                   │
│     → Clicks [Join as Agent A]                                          │
│     → Agent A backend stores private info, marks ready                  │
│                                                                          │
│  3. User opens /agent-b tab (or shares link with Party B)               │
│     → Same process as Agent A                                           │
│                                                                          │
│  4. Arena frontend polls /api/session/status                            │
│     → When both agents ready: enables [Start Negotiation] button        │
│                                                                          │
│                                                                          │
│  PHASE 2: NEGOTIATION                                                   │
│  ════════════════════                                                   │
│                                                                          │
│  5. User clicks [Start Negotiation] in Arena                            │
│     → Arena backend begins orchestration loop                           │
│                                                                          │
│  6. For each turn:                                                      │
│     a. Arena calls Agent A: POST :8001/api/turn                         │
│        → Agent A generates thinking (logged to MongoDB)                 │
│        → Agent A returns public message only                            │
│                                                                          │
│     b. Arena calls Agent B: POST :8002/api/turn                         │
│        → Same process                                                   │
│                                                                          │
│     c. Arena runs Judge                                                 │
│        → Judge sees only public messages                                │
│        → Returns: progress_score, is_consensus, is_deadlock             │
│                                                                          │
│     d. Arena streams turn result via SSE to all connected frontends     │
│                                                                          │
│  7. Agent frontends poll /api/audit to display thinking steps           │
│                                                                          │
│                                                                          │
│  PHASE 3: COMPLETION                                                    │
│  ═══════════════════                                                    │
│                                                                          │
│  8. When Judge declares consensus or deadlock:                          │
│     → Arena streams "complete" event                                    │
│     → All frontends show final result                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# Part 4: API Contracts

## Arena Backend (localhost:8000)

```yaml
POST /api/session/create
  Request:  { goal: string }
  Response: { session_id: string, status: "waiting_for_agents" }

GET /api/session/{session_id}/status
  Response: {
    session_id: string,
    goal: string,
    agent_a_ready: boolean,
    agent_b_ready: boolean,
    status: "waiting" | "ready" | "in_progress" | "consensus" | "deadlock",
    current_turn: number
  }

POST /api/session/{session_id}/start
  Response: { status: "started" }
  Note: Begins the negotiation loop. Fails if agents not ready.

GET /api/session/{session_id}/stream
  Response: SSE stream
  Events:
    { type: "turn", turn: number, agent_a_message: string, agent_b_message: string, judge: object }
    { type: "complete", status: "consensus" | "deadlock", conclusion: string }

GET /api/session/{session_id}/history
  Response: { goal: string, turns: array, status: string }
```

## Agent Backend (localhost:8001 for A, 8002 for B)

```yaml
POST /api/join
  Request:  { session_id: string, private_info: string }
  Response: { agent_id: "A" | "B", ready: true }
  Note: Stores private_info in memory, notifies Arena this agent is ready.

POST /api/turn
  Request:  { session_id: string, goal: string, history: array, turn_number: number }
  Response: { message: string }
  Note: Called by Arena. Generates thinking, logs to MongoDB, returns public message.

GET /api/audit/{session_id}
  Response: {
    audit_trail: [
      {
        turn: number,
        thinking_steps: array,
        strategy: string,
        batna_analysis: string,
        ci_gateway_log: [
          { original: string, action: "ALLOW" | "BLOCK" | "TRANSFORM", reason: string }
        ],
        timestamp: string
      }
    ]
  }
  Note: Called by agent's own frontend to display thinking + CI Gateway decisions.

GET /api/health
  Response: { status: "ok", agent_id: "A" | "B" }
```

---

# Part 5: Agent Backend Implementation

## Key Design: Session-Based State

```python
# agent-backend/app/main.py
import os
from fastapi import FastAPI, HTTPException
from datetime import datetime

app = FastAPI()

AGENT_ID = os.getenv("AGENT_ID", "A")  # Set via environment
ARENA_URL = os.getenv("ARENA_URL", "http://localhost:8000")
AUDIT_COLLECTION = f"agent_{AGENT_ID.lower()}_audit"

# Session-based storage (supports multiple concurrent negotiations)
sessions: dict[str, dict] = {}

@app.post("/api/join")
async def join_session(request: JoinRequest):
    """Store private info for this session."""
    sessions[request.session_id] = {
        "private_info": request.private_info,
        "joined_at": datetime.utcnow()
    }

    # Notify Arena that this agent is ready
    await http_client.post(
        f"{ARENA_URL}/api/session/{request.session_id}/agent-ready",
        json={"agent_id": AGENT_ID}
    )

    return {"agent_id": AGENT_ID, "ready": True}

@app.post("/api/turn")
async def handle_turn(request: TurnRequest):
    """Generate response for a negotiation turn."""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # 1. Generate thinking steps using LLM
    thinking = await generate_thinking(
        private_info=session["private_info"],
        goal=request.goal,
        history=request.history,
        turn=request.turn_number
    )

    # 2. Log thinking to MongoDB (private audit trail)
    await db[AUDIT_COLLECTION].insert_one({
        "session_id": request.session_id,
        "turn": request.turn_number,
        "timestamp": datetime.utcnow(),
        "thinking_steps": thinking["steps"],
        "strategy": thinking["strategy"]
    })

    # 3. Generate public response using LLM
    public_message = await generate_public_response(
        thinking=thinking,
        goal=request.goal,
        history=request.history
    )

    # 4. Return ONLY the public message
    return {"message": public_message}
```

## Agent Processing Pipeline

Each turn, the agent runs this pipeline (all on its own server):

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT TURN PIPELINE                       │
│                  (runs on agent's server)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. RECEIVE from Arena                                      │
│     └─ goal, history, turn_number (public info only)        │
│                                                              │
│  2. LOAD private state                                      │
│     └─ private_info, BATNA, constraints                     │
│                                                              │
│  3. GENERATE THINKING (LLM call)                            │
│     └─ Analyze opponent's position                          │
│     └─ Consider my constraints                              │
│     └─ Select strategy                                      │
│                                                              │
│  4. GENERATE RESPONSE (LLM call)                            │
│     └─ Draft public message                                 │
│                                                              │
│  5. CI GATEWAY FILTER                                       │
│     └─ Check for BATNA leaks → BLOCK                        │
│     └─ Check for desperation signals → TRANSFORM            │
│     └─ Log all decisions to audit trail                     │
│                                                              │
│  6. BATNA VALIDATION                                        │
│     └─ If accepting a deal: is it >= BATNA?                 │
│     └─ If not: reject and counter-propose                   │
│                                                              │
│  7. RETURN to Arena                                         │
│     └─ public message only (filtered)                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Code Implementation

```python
async def generate_thinking(private_info: str, goal: str, history: list, turn: int) -> dict:
    """Generate agent's internal reasoning (never shared with opponent)."""

    prompt = f"""You are a negotiation agent. Think through your strategy.

GOAL: {goal}

YOUR PRIVATE INFORMATION (only you know this):
{private_info}

CONVERSATION SO FAR:
{format_history(history)}

This is turn {turn}. Think step-by-step:
1. What did the opponent's last message reveal about their position?
2. What are my constraints based on my private information?
3. What is my BATNA (walk-away point)? What alternatives do I have?
4. What strategy should I use this turn?
5. What should I say publicly (without revealing my private constraints)?

Respond in JSON:
{{
  "steps": ["step 1 thinking...", "step 2 thinking...", ...],
  "strategy": "name of strategy",
  "batna_analysis": "my walk-away point and why",
  "key_insight": "main takeaway"
}}"""

    response = await llm.invoke(prompt)
    return parse_json(response)

async def apply_ci_gateway(raw_response: str, private_info: str) -> dict:
    """Filter response through Contextual Integrity Gateway."""

    prompt = f"""Review this negotiation message for information leaks.

PROPOSED MESSAGE: {raw_response}

PRIVATE INFO THAT MUST NOT LEAK:
{private_info}

Check for:
1. Direct mention of walk-away price/BATNA
2. Desperation signals (urgent deadlines, low runway)
3. Exact financial figures that reveal constraints

For each issue found, suggest a transformation.

Respond in JSON:
{{
  "filtered_message": "the safe version of the message",
  "decisions": [
    {{"original": "...", "action": "ALLOW|BLOCK|TRANSFORM", "reason": "..."}}
  ]
}}"""

    response = await llm.invoke(prompt)
    return parse_json(response)

async def validate_against_batna(response: str, batna_value: float, history: list) -> bool:
    """Ensure we never accept a deal below our BATNA."""

    # Check if this response accepts a specific value
    if is_acceptance(response, history):
        accepted_value = extract_value(response, history)
        if accepted_value < batna_value:
            return False  # Reject - below BATNA
    return True  # OK to send
```

---

# Part 6: Arena Backend Implementation

```python
# arena-backend/app/main.py
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

AGENT_A_URL = os.getenv("AGENT_A_URL", "http://localhost:8001")
AGENT_B_URL = os.getenv("AGENT_B_URL", "http://localhost:8002")

# Session storage
sessions: dict[str, dict] = {}

@app.post("/api/session/create")
async def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "goal": request.goal,
        "agent_a_ready": False,
        "agent_b_ready": False,
        "status": "waiting",
        "turns": [],
        "current_turn": 0
    }

    # Store in MongoDB
    await db["public_sessions"].insert_one({
        "session_id": session_id,
        "goal": request.goal,
        "status": "waiting",
        "created_at": datetime.utcnow()
    })

    return {"session_id": session_id, "status": "waiting_for_agents"}

@app.post("/api/session/{session_id}/agent-ready")
async def agent_ready(session_id: str, request: AgentReadyRequest):
    """Called by agent backends when they join."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if request.agent_id == "A":
        session["agent_a_ready"] = True
    else:
        session["agent_b_ready"] = True

    if session["agent_a_ready"] and session["agent_b_ready"]:
        session["status"] = "ready"

    return {"status": session["status"]}

@app.post("/api/session/{session_id}/start")
async def start_negotiation(session_id: str, background_tasks: BackgroundTasks):
    session = sessions.get(session_id)
    if session["status"] != "ready":
        raise HTTPException(400, "Agents not ready")

    session["status"] = "in_progress"

    # Run negotiation in background
    background_tasks.add_task(run_negotiation, session_id)

    return {"status": "started"}

async def run_negotiation(session_id: str):
    """Main negotiation loop."""
    session = sessions[session_id]
    max_turns = 10

    for turn in range(1, max_turns + 1):
        session["current_turn"] = turn

        # Get Agent A's response
        a_response = await http_client.post(
            f"{AGENT_A_URL}/api/turn",
            json={
                "session_id": session_id,
                "goal": session["goal"],
                "history": session["turns"],
                "turn_number": turn
            }
        )
        agent_a_message = a_response.json()["message"]

        # Get Agent B's response
        b_response = await http_client.post(
            f"{AGENT_B_URL}/api/turn",
            json={
                "session_id": session_id,
                "goal": session["goal"],
                "history": session["turns"] + [{"agent": "A", "message": agent_a_message}],
                "turn_number": turn
            }
        )
        agent_b_message = b_response.json()["message"]

        # Run Judge
        judge_result = await run_judge(
            goal=session["goal"],
            history=session["turns"],
            agent_a_message=agent_a_message,
            agent_b_message=agent_b_message
        )

        # Store turn
        turn_data = {
            "turn": turn,
            "agent_a_message": agent_a_message,
            "agent_b_message": agent_b_message,
            "judge": judge_result
        }
        session["turns"].append(turn_data)

        # Update MongoDB
        await db["public_sessions"].update_one(
            {"session_id": session_id},
            {"$push": {"turns": turn_data}, "$set": {"current_turn": turn}}
        )

        # Broadcast to SSE listeners
        await broadcast_event(session_id, {"type": "turn", **turn_data})

        # Check for completion
        if judge_result["is_consensus"]:
            session["status"] = "consensus"
            await broadcast_event(session_id, {
                "type": "complete",
                "status": "consensus",
                "conclusion": judge_result["summary"]
            })
            break

        if judge_result["is_deadlock"]:
            session["status"] = "deadlock"
            await broadcast_event(session_id, {
                "type": "complete",
                "status": "deadlock",
                "conclusion": "Negotiation reached deadlock"
            })
            break
```

---

# Part 7: Frontend Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx              # Redirects to /arena
│   ├── arena/
│   │   └── page.tsx          # Create session, view public conversation
│   ├── agent-a/
│   │   └── page.tsx          # Join as A, view A's thinking
│   └── agent-b/
│       └── page.tsx          # Join as B, view B's thinking
├── components/
│   ├── PrivateInfoInput.tsx  # Textarea for private constraints
│   ├── ThinkingDisplay.tsx   # Shows agent's thinking steps
│   ├── ConversationView.tsx  # Public message history
│   └── StatusBadge.tsx       # Session status indicator
└── lib/
    └── api.ts                # API client with backend URLs
```

## API Client Configuration

```typescript
// lib/api.ts
const ARENA_API = process.env.NEXT_PUBLIC_ARENA_URL || 'http://localhost:8000'
const AGENT_A_API = process.env.NEXT_PUBLIC_AGENT_A_URL || 'http://localhost:8001'
const AGENT_B_API = process.env.NEXT_PUBLIC_AGENT_B_URL || 'http://localhost:8002'

export const arenaApi = {
  createSession: (goal: string) =>
    fetch(`${ARENA_API}/api/session/create`, { method: 'POST', body: JSON.stringify({ goal }) }),

  getStatus: (sessionId: string) =>
    fetch(`${ARENA_API}/api/session/${sessionId}/status`),

  startNegotiation: (sessionId: string) =>
    fetch(`${ARENA_API}/api/session/${sessionId}/start`, { method: 'POST' }),

  streamEvents: (sessionId: string) =>
    new EventSource(`${ARENA_API}/api/session/${sessionId}/stream`)
}

export const agentApi = (baseUrl: string) => ({
  join: (sessionId: string, privateInfo: string) =>
    fetch(`${baseUrl}/api/join`, { method: 'POST', body: JSON.stringify({ session_id: sessionId, private_info: privateInfo }) }),

  getAudit: (sessionId: string) =>
    fetch(`${baseUrl}/api/audit/${sessionId}`)
})

export const agentAApi = agentApi(AGENT_A_API)
export const agentBApi = agentApi(AGENT_B_API)
```

## Agent Page (Polling for Audit Trail)

```typescript
// app/agent-a/page.tsx
'use client'
import { useState, useEffect } from 'react'
import { agentAApi, arenaApi } from '@/lib/api'

export default function AgentAPage() {
  const [sessionId, setSessionId] = useState('')
  const [privateInfo, setPrivateInfo] = useState('')
  const [joined, setJoined] = useState(false)
  const [auditTrail, setAuditTrail] = useState([])
  const [conversation, setConversation] = useState([])

  // Join session
  const handleJoin = async () => {
    await agentAApi.join(sessionId, privateInfo)
    setJoined(true)
  }

  // Poll for audit trail updates every 2 seconds
  useEffect(() => {
    if (!joined) return

    const interval = setInterval(async () => {
      const audit = await agentAApi.getAudit(sessionId).then(r => r.json())
      setAuditTrail(audit.audit_trail)

      const status = await arenaApi.getStatus(sessionId).then(r => r.json())
      setConversation(status.turns || [])
    }, 2000)

    return () => clearInterval(interval)
  }, [joined, sessionId])

  return (
    <div>
      <h1>Agent A - Private View</h1>

      {!joined ? (
        <div>
          <input
            placeholder="Session ID"
            value={sessionId}
            onChange={e => setSessionId(e.target.value)}
          />
          <textarea
            placeholder="Enter your private constraints..."
            value={privateInfo}
            onChange={e => setPrivateInfo(e.target.value)}
          />
          <button onClick={handleJoin}>Join as Agent A</button>
        </div>
      ) : (
        <div>
          <section>
            <h2>Your Thinking (Private)</h2>
            {auditTrail.map((entry, i) => (
              <div key={i}>
                <h3>Turn {entry.turn}</h3>
                <ul>
                  {entry.thinking_steps.map((step, j) => <li key={j}>{step}</li>)}
                </ul>
                <p><strong>Strategy:</strong> {entry.strategy}</p>
                <p><strong>BATNA Analysis:</strong> {entry.batna_analysis}</p>

                {/* CI Gateway Log - shows what was filtered */}
                <div className="ci-gateway-log">
                  <h4>CI Gateway Decisions:</h4>
                  {entry.ci_gateway_log?.map((decision, k) => (
                    <div key={k} className={`ci-decision ci-${decision.action.toLowerCase()}`}>
                      <span className="action">{decision.action}</span>
                      <span className="reason">{decision.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>

          <section>
            <h2>Public Conversation</h2>
            {conversation.map((turn, i) => (
              <div key={i}>
                <p><strong>You:</strong> {turn.agent_a_message}</p>
                <p><strong>Agent B:</strong> {turn.agent_b_message}</p>
              </div>
            ))}
          </section>
        </div>
      )}
    </div>
  )
}
```

---

# Part 8: Project Structure

```
agent-orchestration/
│
├── agent-backend/                  # Run twice with AGENT_ID=A/B
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── agent.py                # Thinking & response generation
│   │   ├── db.py                   # MongoDB connection
│   │   └── models.py               # Pydantic models
│   ├── requirements.txt
│   └── .env.example
│
├── arena-backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── orchestrator.py         # Turn coordination
│   │   ├── judge.py                # Judge logic
│   │   ├── db.py                   # MongoDB connection
│   │   └── models.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                       # Next.js app
│   ├── app/
│   │   ├── arena/page.tsx
│   │   ├── agent-a/page.tsx
│   │   └── agent-b/page.tsx
│   ├── components/
│   ├── lib/api.ts
│   ├── package.json
│   └── .env.local
│
├── start-all.sh
└── README.md
```

---

# Part 9: Environment Variables

## agent-backend/.env.example
```bash
AGENT_ID=A                          # "A" or "B" - set per instance
ANTHROPIC_API_KEY=sk-ant-...
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=agent_orchestration
ARENA_URL=http://localhost:8000
PORT=8001                           # 8001 for A, 8002 for B
```

## arena-backend/.env.example
```bash
ANTHROPIC_API_KEY=sk-ant-...
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=agent_orchestration
AGENT_A_URL=http://localhost:8001
AGENT_B_URL=http://localhost:8002
PORT=8000
```

## frontend/.env.local
```bash
NEXT_PUBLIC_ARENA_URL=http://localhost:8000
NEXT_PUBLIC_AGENT_A_URL=http://localhost:8001
NEXT_PUBLIC_AGENT_B_URL=http://localhost:8002
```

---

# Part 10: Quick Start

```bash
#!/bin/bash
# start-all.sh

# Start Agent A backend
cd agent-backend
AGENT_ID=A PORT=8001 uvicorn app.main:app --port 8001 &

# Start Agent B backend
AGENT_ID=B PORT=8002 uvicorn app.main:app --port 8002 &

# Start Arena backend
cd ../arena-backend
uvicorn app.main:app --port 8000 &

# Start frontend
cd ../frontend
npm run dev &

echo "Services started:"
echo "  Arena:    http://localhost:3000/arena"
echo "  Agent A:  http://localhost:3000/agent-a"
echo "  Agent B:  http://localhost:3000/agent-b"
```

---

# Part 11: Implementation Checklist

| Phase | Task | Complexity |
|-------|------|------------|
| **1. Agent Backend** | FastAPI scaffold with AGENT_ID config | Low |
| | `/api/join` endpoint | Low |
| | `/api/turn` with thinking generation | Medium |
| | BATNA analysis in thinking prompt | Low |
| | CI Gateway filter implementation | Medium |
| | BATNA validation (reject bad deals) | Low |
| | `/api/audit` endpoint with CI log | Low |
| | MongoDB audit writes | Low |
| **2. Arena Backend** | FastAPI scaffold | Low |
| | `/api/session/create` and status endpoints | Low |
| | Orchestration loop calling agent backends | Medium |
| | Judge implementation | Medium |
| | SSE streaming | Low |
| **3. Frontend** | Next.js scaffold with routing | Low |
| | Arena page (create session, view conversation) | Medium |
| | Agent pages (join, view thinking + CI log) | Medium |
| | CI Gateway log visualization | Low |
| | Polling for real-time updates | Low |
| **4. Integration** | End-to-end testing | Medium |
| | Start script | Low |

**Estimated total: ~14 hours**

---

# Part 12: Key Points for Judges

## What Makes This Novel

| Innovation | Why It Matters |
|------------|----------------|
| **Physical Separation** | Privacy isn't a prompt instruction—it's architectural. Agent A's BATNA literally cannot leak to Agent B because it's on a different server. |
| **BATNA Validation** | Agents never accept deals below their walk-away point. This happens automatically, verified by the audit trail. |
| **Contextual Integrity Gateway** | Each agent decides what to share BEFORE sending. You can see exactly what was blocked/transformed in the audit log. |
| **Verifiable Audit Trail** | MongoDB stores each agent's reasoning privately. Judges can verify decisions without compromising privacy. |

## The Demo Story (3 minutes)

**Setup (30 sec):**
> "When AI agents negotiate, they need to share information to find deals. But sharing too much—like your walk-away price—lets the other side exploit you. We solved this with physical separation."

**Demo (2 min):**
> Open three browser tabs: Agent A (startup), Agent B (investor), Arena (neutral).
>
> "Agent A enters their private constraints: minimum valuation $10M, 8 months runway. This stays on Agent A's server."
>
> "Agent B enters their constraints: max check $12M, fund closing soon. This stays on Agent B's server."
>
> "Watch the negotiation in the Arena—only public messages appear."
>
> "Now look at Agent A's tab. You can see their THINKING: 'My BATNA is $8M, so I won't accept below that.' And the CI Gateway log shows: 'BLOCKED mention of runway—transformed to limited runway.'"
>
> "Agent B has completely different thinking that Agent A never sees."

**Close (30 sec):**
> "This is Privacy Through Physical Separation with a full audit trail. Each agent's reasoning is logged for transparency, but that reasoning never crosses to the other side."

## Trade-offs Acknowledged

| Trade-off | Why It's Worth It |
|-----------|------------------|
| Multiple services to run | Clear, verifiable privacy boundaries |
| Extra LLM calls for CI Gateway | Prevents catastrophic information leaks |
| More complex than single-server | "Can't leak" beats "won't leak" |
