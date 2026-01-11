/**
 * API client for the Negotiation Arena
 */

// API base URLs (use proxies in Next.js config)
const ARENA_API = '/api/arena'
const AGENT_A_API = '/api/agent-a'
const AGENT_B_API = '/api/agent-b'

// Types
export interface SessionStatus {
  session_id: string
  goal: string
  agent_a_ready: boolean
  agent_b_ready: boolean
  status: 'waiting' | 'ready' | 'in_progress' | 'consensus' | 'deadlock'
  current_turn: number
}

export interface JudgeEvaluation {
  progress: boolean
  progress_score: number
  is_deadlock: boolean
  is_consensus: boolean
  reasoning: string
  consensus_summary: string | null
}

export interface TurnData {
  turn: number
  agent_a_message: string
  agent_b_message: string
  judge: JudgeEvaluation
}

export interface CIGatewayDecision {
  original: string
  action: 'ALLOW' | 'BLOCK' | 'TRANSFORM'
  result: string | null
  reason: string
}

export interface BATNAAnalysis {
  batna_value: number | null
  batna_description: string
  current_offer_acceptable: boolean
  reasoning: string
}

export interface AuditEntry {
  turn: number
  timestamp: string
  thinking_steps: string[]
  strategy: string
  batna_analysis: BATNAAnalysis
  ci_gateway_log: {
    original_message: string
    filtered_message: string
    decisions: CIGatewayDecision[]
  }
  final_message: string
}

// Arena API
export const arenaApi = {
  async createSession(goal: string): Promise<{ session_id: string; status: string }> {
    const res = await fetch(`${ARENA_API}/session/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal }),
    })
    if (!res.ok) throw new Error('Failed to create session')
    return res.json()
  },

  async getStatus(sessionId: string): Promise<SessionStatus> {
    const res = await fetch(`${ARENA_API}/session/${sessionId}/status`)
    if (!res.ok) throw new Error('Failed to get session status')
    return res.json()
  },

  async startNegotiation(sessionId: string): Promise<{ status: string }> {
    const res = await fetch(`${ARENA_API}/session/${sessionId}/start`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error('Failed to start negotiation')
    return res.json()
  },

  streamEvents(sessionId: string): EventSource {
    return new EventSource(`${ARENA_API}/session/${sessionId}/stream`)
  },

  async getHistory(sessionId: string): Promise<{
    session_id: string
    goal: string
    turns: TurnData[]
    status: string
    final_conclusion: string | null
  }> {
    const res = await fetch(`${ARENA_API}/session/${sessionId}/history`)
    if (!res.ok) throw new Error('Failed to get history')
    return res.json()
  },

  async health(): Promise<{ status: string; services: Record<string, string> }> {
    const res = await fetch(`${ARENA_API}/health`)
    if (!res.ok) throw new Error('Failed to check health')
    return res.json()
  },
}

// Agent API (factory for A and B)
const createAgentApi = (baseUrl: string) => ({
  async join(sessionId: string, privateInfo: string): Promise<{ agent_id: string; ready: boolean }> {
    const res = await fetch(`${baseUrl}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, private_info: privateInfo }),
    })
    if (!res.ok) throw new Error('Failed to join session')
    return res.json()
  },

  async getAudit(sessionId: string): Promise<{ session_id: string; agent_id: string; audit_trail: AuditEntry[] }> {
    const res = await fetch(`${baseUrl}/audit/${sessionId}`)
    if (!res.ok) throw new Error('Failed to get audit trail')
    return res.json()
  },

  async health(): Promise<{ status: string; agent_id: string }> {
    const res = await fetch(`${baseUrl}/health`)
    if (!res.ok) throw new Error('Failed to check health')
    return res.json()
  },
})

export const agentAApi = createAgentApi(AGENT_A_API)
export const agentBApi = createAgentApi(AGENT_B_API)
