# Agent Negotiation Arena

A multi-agent negotiation system demonstrating AI agents negotiating with each other based on private information. Two agents (A and B) negotiate turn-by-turn while a Judge evaluates progress, detects deadlocks, and identifies consensus.

## Features

- **Three-Agent System**: Agent A, Agent B, and an impartial Judge
- **Private Information**: Each agent has confidential constraints invisible to the other
- **Turn-Based Negotiation**: Structured back-and-forth dialogue
- **Progress Tracking**: Judge evaluates each turn with a progress score (0-10)
- **Automatic Termination**: Detects consensus (agreement reached) or deadlock (no progress)
- **Real-Time Streaming**: Watch negotiations unfold turn by turn
- **Modern UI**: Split-window interface for easy configuration

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Anthropic API key

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## How It Works

### Negotiation Flow

```
┌───────────────────────────────────────────────────────────────┐
│                      USER INPUT                                │
│  Goal + Agent A Private Info + Agent B Private Info           │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                    NEGOTIATION LOOP                            │
│  1. Agent A makes statement/proposal                          │
│  2. Agent B responds                                          │
│  3. Judge evaluates: PROGRESS / DEADLOCK / CONSENSUS          │
│  4. If PROGRESS → Continue loop                               │
│     If DEADLOCK → End with deadlock message                   │
│     If CONSENSUS → End with agreement summary                 │
└───────────────────────────────────────────────────────────────┘
```

### Example Use Cases

**Car Sale Negotiation**
- Goal: Agree on a fair price for a used car
- Agent A (Buyer): Budget $15,000, noticed scratches
- Agent B (Seller): Minimum $12,000, recent maintenance done

**Salary Negotiation**
- Goal: Agree on compensation for a new hire
- Agent A (Candidate): Wants $150k, has other offers
- Agent B (Employer): Budget $140k, can offer equity

**Resource Allocation**
- Goal: Divide a shared budget between departments
- Agent A (Marketing): Needs $50k for campaign
- Agent B (Engineering): Needs $40k for infrastructure

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/negotiate/start` | Start a new negotiation session |
| POST | `/api/negotiate/step` | Execute one negotiation round |
| POST | `/api/negotiate/run` | Run full negotiation until completion |
| POST | `/api/negotiate/stream` | Stream negotiation via Server-Sent Events |
| GET | `/api/negotiate/status/{session_id}` | Get negotiation status |
| GET | `/api/health` | Health check |

## Architecture

```
Frontend (React + Vite)
    │
    ├── Split-window UI for agent configuration
    ├── Real-time negotiation transcript
    └── Progress visualization
    │
    ▼
Backend (FastAPI)
    │
    ├── Negotiation session management
    ├── SSE streaming for real-time updates
    └── In-memory session storage
    │
    ▼
Agent System (LangChain)
    │
    ├── Agent A: Negotiator with private info
    ├── Agent B: Negotiator with private info
    └── Judge: Progress evaluator
    │
    ▼
Claude API (Anthropic)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `MAX_NEGOTIATION_TURNS` | 10 | Maximum turns before forced end |
| `DEADLOCK_THRESHOLD` | 3 | No-progress turns before deadlock |
| `DEBUG` | true | Enable debug logging |

## Project Structure

```
agent-orchestration/
├── backend/
│   ├── app/
│   │   ├── agents/        # Agent A, Agent B, Judge
│   │   ├── api/           # FastAPI routes
│   │   ├── core/          # Configuration
│   │   ├── db/            # Pydantic models
│   │   └── main.py        # Application entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   └── index.css      # Styles
│   └── package.json
├── SPECIFICATION.md       # Detailed system specification
├── CLAUDE.md              # AI coding agent guide
└── README.md
```

## Tech Stack

- **Backend**: FastAPI, LangChain, Anthropic Claude
- **Frontend**: React, Vite
- **Styling**: CSS with CSS Variables

## Verification

### Check Backend Health

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "anthropic": "configured",
  "errors": []
}
```

### Test Negotiation

```bash
curl -X POST http://localhost:8000/api/negotiate/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Agree on a fair price for the car",
    "agent_a_info": "Buyer. Max budget $15,000",
    "agent_b_info": "Seller. Min price $12,000"
  }'
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "ANTHROPIC_API_KEY not set" | Add key to `.env` file |
| "Cannot connect to backend" | Run `uvicorn app.main:app` |
| CORS Errors | Check frontend origin in `main.py` |
| Negotiation stuck | Check `MAX_NEGOTIATION_TURNS` setting |

## License

MIT
