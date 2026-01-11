# Privacy-Preserving Multi-Agent Negotiation Framework

A demonstration of **privacy through physical separation** in AI agent negotiations. Each agent runs on its own backend server, ensuring private information cannot leak to the other party.

## The Problem

When AI agents negotiate, they must share information to find deals. But sharing too much (like walk-away prices) destroys negotiating power. LLMs are notoriously bad at keeping secrets when instructed via prompts.

## Our Solution

**Physical separation**: Each agent runs on its own isolated backend server. Agent A's private data *cannot* reach Agent B because it never leaves Agent A's server.

## Key Innovations

| Innovation | What It Does | Why It Matters |
|------------|--------------|----------------|
| **Physical Separation** | Each agent runs in its own backend | Privacy through architecture, not prompts |
| **BATNA Calculator** | Computes walk-away value privately | Agent never accepts deals below this threshold |
| **CI Gateway** | Filters outgoing messages for leaks | Blocks/transforms sensitive information |
| **MongoDB Audit Trail** | Logs each agent's thinking privately | Verifiable decisions without data leakage |

## Architecture

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ Agent A Backend     │  │ Agent B Backend     │  │ Arena Backend       │
│ localhost:8001      │  │ localhost:8002      │  │ localhost:8000      │
│                     │  │                     │  │                     │
│ • Alex's private    │  │ • Jordan's private  │  │ • Orchestrates      │
│   info stays here   │  │   info stays here   │  │ • Runs Judge        │
│ • BATNA calculated  │  │ • BATNA calculated  │  │ • Only sees public  │
│ • CI Gateway filter │  │ • CI Gateway filter │  │   messages          │
│ • Audit to MongoDB  │  │ • Audit to MongoDB  │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Next.js Frontend      │
                     │   localhost:3000        │
                     │                         │
                     │   /arena   → Public     │
                     │   /agent-a → Alex view  │
                     │   /agent-b → Jordan view│
                     └─────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Anthropic API key

### 1. Configure Environment

Copy the example environment files and add your credentials:

```bash
# Agent Backend
cp agent-backend/.env.example agent-backend/.env
# Edit agent-backend/.env with your ANTHROPIC_API_KEY and MONGODB_URI

# Arena Backend
cp arena-backend/.env.example arena-backend/.env
# Edit arena-backend/.env with your ANTHROPIC_API_KEY and MONGODB_URI
```

### 2. Start All Services

Use the provided startup script:

```bash
./start-all.sh
```

Or start services manually:

```bash
# Terminal 1: Agent A Backend
cd agent-backend
source venv/bin/activate
AGENT_ID=A PORT=8001 uvicorn app.main:app --port 8001

# Terminal 2: Agent B Backend
cd agent-backend
source venv/bin/activate
AGENT_ID=B PORT=8002 uvicorn app.main:app --port 8002

# Terminal 3: Arena Backend
cd arena-backend
source venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 4: Frontend
cd frontend-next
npm run dev
```

### 3. Run the Demo

Open three browser tabs:

1. **http://localhost:3000/arena** - Create session, watch public negotiation
2. **http://localhost:3000/agent-a** - Alex's private view (thinking, BATNA, CI Gateway)
3. **http://localhost:3000/agent-b** - Jordan's private view

## Demo Scenario: Family Trust Fund

Two partners (Alex and Jordan) negotiate monthly contributions to a family trust fund:

**Alex (Partner A)** has constraints:
- Income: $8,500/month after taxes
- Student loans: $800/month
- Maximum contribution: $4,000/month
- **BATNA**: Won't accept above $3,500/month

**Jordan (Partner B)** has constraints:
- Income: $12,000/month after taxes
- No debt payments
- Wants at least $5,000/month total in the fund
- **BATNA**: Alex must contribute at least $2,500/month

Watch how each agent:
1. Thinks through strategy privately
2. Has their BATNA calculated automatically
3. Gets messages filtered by the CI Gateway
4. Never reveals sensitive information

## Project Structure

```
agent-orchestration/
├── agent-backend/        # Runs twice (Agent A & B)
│   ├── app/
│   │   ├── main.py       # FastAPI endpoints
│   │   ├── agent.py      # Thinking, BATNA, CI Gateway
│   │   ├── db.py         # MongoDB connection
│   │   └── models.py     # Pydantic models
│   └── requirements.txt
├── arena-backend/        # Orchestration service
│   ├── app/
│   │   ├── main.py       # FastAPI + SSE streaming
│   │   ├── judge.py      # Judge evaluation logic
│   │   └── models.py
│   └── requirements.txt
├── frontend-next/        # Next.js 14 app
│   ├── app/
│   │   ├── arena/        # Public view
│   │   ├── agent-a/      # Alex's private view
│   │   └── agent-b/      # Jordan's private view
│   └── lib/api.ts
└── start-all.sh          # Start all services
```

## API Endpoints

### Arena Backend (port 8000)
- `POST /api/session/create` - Create new session
- `GET /api/session/{id}/status` - Get session status
- `POST /api/session/{id}/start` - Start negotiation
- `GET /api/session/{id}/stream` - SSE event stream

### Agent Backend (ports 8001, 8002)
- `POST /api/join` - Join with private info
- `POST /api/turn` - Generate response (called by Arena)
- `GET /api/audit/{id}` - Get thinking audit trail

## How It Works

### Turn Pipeline (on agent's server)
1. **Receive** goal + history from Arena
2. **Load** private info from memory
3. **Generate thinking** via LLM (logged to MongoDB)
4. **Calculate BATNA** from private constraints
5. **Generate response** based on strategy
6. **CI Gateway filter** blocks/transforms leaks
7. **BATNA validation** ensures no bad deals accepted
8. **Return** only the filtered public message

### Privacy Guarantees
- Private info stored only in agent's backend memory
- MongoDB audit collections are per-agent
- CI Gateway filters before any network transmission
- Arena only receives public messages

## MongoDB Collections

- `agent_a_audit` - Alex's private thinking trail
- `agent_b_audit` - Jordan's private thinking trail
- `public_sessions` - Only public messages visible

## The Demo Story (3 minutes)

**Setup (30 sec):**
> "When AI agents negotiate, they need to share information to find deals. But sharing too much—like your walk-away price—lets the other side exploit you. We solved this with physical separation."

**Demo (2 min):**
> Open three browser tabs: Agent A (Alex), Agent B (Jordan), Arena (neutral).
>
> "Alex enters their private constraints: max contribution $4,000, student loans $800/month. This stays on Agent A's server."
>
> "Jordan enters their constraints: income $12,000, wants at least $5,000 total in fund. This stays on Agent B's server."
>
> "Watch the negotiation in the Arena—only public messages appear."
>
> "Now look at Alex's tab. You can see their THINKING: 'My BATNA is $3,500, so I won't accept above that.' And the CI Gateway log shows what was filtered."
>
> "Jordan has completely different thinking that Alex never sees."

**Close (30 sec):**
> "This is Privacy Through Physical Separation with a full audit trail. Each agent's reasoning is logged for transparency, but that reasoning never crosses to the other side."

## License

MIT
