# Multi-Agent Negotiation System Specification

## Overview

A web application demonstrating AI agents negotiating with each other based on private information. Two agents (A and B) negotiate turn-by-turn while a Judge evaluates progress, detects deadlocks, and identifies consensus.

## Core Concepts

### Agents

1. **Agent A (Negotiator)**
   - Has access only to their private information provided by the user
   - Negotiates with Agent B to reach the goal
   - Cannot see Agent B's private information
   - Makes proposals and counter-proposals

2. **Agent B (Negotiator)**
   - Has access only to their private information provided by the user
   - Negotiates with Agent A to reach the goal
   - Cannot see Agent A's private information
   - Makes proposals and counter-proposals

3. **Judge**
   - Evaluates each turn of negotiation
   - Has access to the goal but NOT the private information
   - Determines:
     - **Progress**: Are agents moving toward the goal?
     - **Deadlock**: No progress for multiple turns, positions entrenched
     - **Consensus**: Agreement reached that satisfies the goal

### Negotiation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INPUT PHASE                         │
├─────────────────────────────────────────────────────────────┤
│  Agent A Private Info  │  Goal  │  Agent B Private Info     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   NEGOTIATION LOOP                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   1. Agent A makes statement/proposal                       │
│                     ↓                                        │
│   2. Judge evaluates A's response                           │
│                     ↓                                        │
│   3. Agent B responds with counter/agreement                │
│                     ↓                                        │
│   4. Judge evaluates B's response                           │
│                     ↓                                        │
│   5. Judge determines: PROGRESS / DEADLOCK / CONSENSUS      │
│                     ↓                                        │
│   If PROGRESS → Continue loop (back to step 1)              │
│   If DEADLOCK → End with deadlock message                   │
│   If CONSENSUS → End with conclusion                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### State Management

```python
NegotiationState = {
    "goal": str,                    # The objective both agents must reach
    "agent_a_info": str,            # Private info for Agent A only
    "agent_b_info": str,            # Private info for Agent B only
    "negotiation_history": list,    # All turns in the negotiation
    "current_turn": int,            # Turn counter
    "status": str,                  # "in_progress" | "deadlock" | "consensus"
    "judge_evaluations": list,      # Judge's assessments
    "final_conclusion": str,        # Final outcome when concluded
    "progress_score": int,          # Track progress (0-10)
    "deadlock_counter": int,        # Consecutive no-progress turns
}
```

## API Design

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/negotiate/start` | Start a new negotiation session |
| POST | `/api/negotiate/step` | Execute one round of negotiation |
| GET | `/api/negotiate/status/{session_id}` | Get current negotiation status |
| GET | `/api/health` | Health check |

### Request/Response Models

#### Start Negotiation
```json
// POST /api/negotiate/start
// Request
{
    "goal": "Agree on a fair price for the used car",
    "agent_a_info": "You are a buyer. Max budget: $15,000. The car has visible scratches.",
    "agent_b_info": "You are the seller. Minimum acceptable: $12,000. Recent maintenance done."
}

// Response
{
    "session_id": "uuid",
    "status": "in_progress",
    "message": "Negotiation started"
}
```

#### Execute Step
```json
// POST /api/negotiate/step
// Request
{
    "session_id": "uuid"
}

// Response
{
    "session_id": "uuid",
    "turn": 1,
    "agent_a_response": "I've seen the car and I'm interested. Given the scratches, I'd offer $11,000.",
    "agent_b_response": "Thank you for your interest. The scratches are minor. With recent maintenance, $14,000 is fair.",
    "judge_evaluation": {
        "progress": true,
        "reasoning": "Both parties have stated initial positions. Negotiation is beginning.",
        "progress_score": 3
    },
    "status": "in_progress",
    "final_conclusion": null
}
```

#### Final States
```json
// Deadlock
{
    "status": "deadlock",
    "final_conclusion": "Negotiation ended in deadlock. Agent A refused to go above $12,000, Agent B refused to go below $14,000. No further progress possible."
}

// Consensus
{
    "status": "consensus",
    "final_conclusion": "Agreement reached: The car will be sold for $13,000. Agent A accepts the price considering the recent maintenance, Agent B accepts considering the visible scratches."
}
```

## Frontend Design

### Layout

```
┌────────────────────────────────────────────────────────────────────┐
│                     AGENT NEGOTIATION ARENA                        │
│                        [Status Badge]                              │
├────────────────────────────────────────────────────────────────────┤
│                         NEGOTIATION GOAL                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ [Text input for the goal both agents must achieve]           │ │
│  └──────────────────────────────────────────────────────────────┘ │
├─────────────────────────┬──────────────────────────────────────────┤
│      AGENT A            │              AGENT B                     │
│   Private Information   │         Private Information              │
│  ┌───────────────────┐  │  ┌────────────────────────────────────┐ │
│  │                   │  │  │                                    │ │
│  │   [Textarea]      │  │  │        [Textarea]                  │ │
│  │                   │  │  │                                    │ │
│  └───────────────────┘  │  └────────────────────────────────────┘ │
├─────────────────────────┴──────────────────────────────────────────┤
│                      [START NEGOTIATION]                           │
├────────────────────────────────────────────────────────────────────┤
│                     NEGOTIATION TRANSCRIPT                         │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Turn 1:                                                      │ │
│  │ ┌─────────────────┐  ┌─────────────────┐                    │ │
│  │ │ Agent A says... │  │ Agent B says... │                    │ │
│  │ └─────────────────┘  └─────────────────┘                    │ │
│  │ Judge: [Evaluation with progress indicator]                  │ │
│  │                                                              │ │
│  │ Turn 2:                                                      │ │
│  │ ...                                                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────┤
│                      FINAL OUTCOME                                 │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ [Consensus/Deadlock message displayed here]                  │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### Visual States

1. **Setup Phase**: Input fields active, no transcript
2. **Negotiating**: Input fields locked, transcript growing, spinner on current turn
3. **Deadlock**: Red banner, transcript complete, final message shown
4. **Consensus**: Green banner, transcript complete, agreement summary shown

## Technical Implementation

### Backend Stack
- FastAPI (existing)
- LangGraph for agent orchestration
- In-memory session storage (no MongoDB)
- Anthropic Claude API

### Frontend Stack
- React with Vite (existing)
- CSS for styling (existing infrastructure)

### Agent Prompts

#### Agent A System Prompt
```
You are Agent A in a negotiation. Your goal is: {goal}

Your private information (ONLY YOU HAVE ACCESS TO THIS):
{agent_a_info}

You must negotiate with Agent B to reach the goal. You cannot reveal your private constraints directly, but you can use them to guide your negotiation strategy.

Based on the negotiation history, provide your next statement or proposal. Be strategic but work toward finding common ground.
```

#### Agent B System Prompt
```
You are Agent B in a negotiation. Your goal is: {goal}

Your private information (ONLY YOU HAVE ACCESS TO THIS):
{agent_b_info}

You must negotiate with Agent A to reach the goal. You cannot reveal your private constraints directly, but you can use them to guide your negotiation strategy.

Based on the negotiation history and Agent A's last statement, provide your response. Be strategic but work toward finding common ground.
```

#### Judge System Prompt
```
You are an impartial Judge evaluating a negotiation between Agent A and Agent B.

The goal of the negotiation is: {goal}

You do NOT have access to either agent's private information. You can only evaluate based on what has been said.

Based on the negotiation history, evaluate:
1. Are the agents making progress toward the goal? (progress: true/false)
2. What is the current progress score? (0-10, where 10 is very close to agreement)
3. Is there a deadlock? (Agents stuck, no movement for multiple turns, positions entrenched)
4. Has consensus been reached? (Both agents agreed on a solution that satisfies the goal)

Respond in JSON format:
{
    "progress": boolean,
    "progress_score": number,
    "is_deadlock": boolean,
    "is_consensus": boolean,
    "reasoning": "Your explanation",
    "consensus_summary": "If consensus reached, summarize the agreement" // optional
}
```

## Configuration

### Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-...   # Required for Claude API
DEBUG=true                      # Optional debug mode
```

### Constants
```python
MAX_TURNS = 10                  # Maximum negotiation rounds
DEADLOCK_THRESHOLD = 3          # Consecutive no-progress turns before deadlock
```

## Example Use Cases

### 1. Car Sale Negotiation
- **Goal**: Agree on a fair price for a used car
- **Agent A (Buyer)**: Budget $15,000, noticed scratches, needs car urgently
- **Agent B (Seller)**: Minimum $12,000, just did maintenance, no rush to sell

### 2. Salary Negotiation
- **Goal**: Agree on a compensation package for a new hire
- **Agent A (Candidate)**: Wants $150k minimum, has other offers
- **Agent B (Employer)**: Budget is $140k, can offer equity

### 3. Resource Allocation
- **Goal**: Divide a shared budget between two departments
- **Agent A (Marketing)**: Needs $50k for campaign, has deadline
- **Agent B (Engineering)**: Needs $40k for infrastructure, critical bugs

## Success Criteria

1. Users can input private information for both agents
2. Agents negotiate without seeing each other's private info
3. Judge correctly identifies progress/deadlock/consensus
4. UI clearly shows negotiation state and outcome
5. System handles edge cases (immediate agreement, quick deadlock)
6. Responsive and intuitive user interface
