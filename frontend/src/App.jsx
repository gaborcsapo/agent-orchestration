import { useState, useEffect, useRef } from 'react'

const API_BASE = '/api'

function App() {
  // Input state
  const [goal, setGoal] = useState('')
  const [agentAInfo, setAgentAInfo] = useState('')
  const [agentBInfo, setAgentBInfo] = useState('')

  // Negotiation state
  const [isNegotiating, setIsNegotiating] = useState(false)
  const [turns, setTurns] = useState([])
  const [status, setStatus] = useState(null) // 'in_progress', 'consensus', 'deadlock'
  const [finalConclusion, setFinalConclusion] = useState(null)
  const [currentTurn, setCurrentTurn] = useState(0)

  // UI state
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)

  const transcriptEndRef = useRef(null)

  // Scroll to bottom when turns change
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  // Check health on mount
  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      const data = await res.json()
      setHealth(data)
      if (data.errors?.length > 0) {
        setError(data.errors.join(' | '))
      }
    } catch (e) {
      setHealth({ status: 'error' })
      setError('Cannot connect to backend. Is the server running?')
    }
  }

  const resetNegotiation = () => {
    setTurns([])
    setStatus(null)
    setFinalConclusion(null)
    setCurrentTurn(0)
    setError(null)
  }

  const startNegotiation = async () => {
    if (!goal.trim() || !agentAInfo.trim() || !agentBInfo.trim()) {
      setError('Please fill in the goal and private information for both agents.')
      return
    }

    resetNegotiation()
    setIsNegotiating(true)
    setStatus('in_progress')

    try {
      // Use the streaming endpoint for real-time updates
      const response = await fetch(`${API_BASE}/negotiate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: goal.trim(),
          agent_a_info: agentAInfo.trim(),
          agent_b_info: agentBInfo.trim(),
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to start negotiation')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'turn') {
                setTurns(prev => [...prev, {
                  turn: data.turn,
                  agentA: data.agent_a_response,
                  agentB: data.agent_b_response,
                  judge: data.judge_evaluation,
                  progressScore: data.progress_score,
                }])
                setCurrentTurn(data.turn)
                setStatus(data.status)
              } else if (data.type === 'complete') {
                setStatus(data.status)
                setFinalConclusion(data.final_conclusion)
              } else if (data.type === 'error') {
                setError(data.message)
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }
    } catch (e) {
      setError(e.message || 'Negotiation failed')
    } finally {
      setIsNegotiating(false)
    }
  }

  const getStatusBadge = () => {
    if (!status) return null

    const badges = {
      in_progress: { text: 'In Progress', className: 'status-badge in-progress' },
      consensus: { text: 'Consensus Reached', className: 'status-badge consensus' },
      deadlock: { text: 'Deadlock', className: 'status-badge deadlock' },
    }

    const badge = badges[status]
    return badge ? <span className={badge.className}>{badge.text}</span> : null
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <h1>Agent Negotiation Arena</h1>
        <div className="header-right">
          {getStatusBadge()}
          <div className="health-indicator">
            <span className={`health-dot ${health?.status === 'healthy' ? 'healthy' : 'unhealthy'}`} />
            <span>{health?.status === 'healthy' ? 'API Connected' : 'API Disconnected'}</span>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* Main Content */}
      <main className="main-content">
        {/* Setup Panel */}
        <section className="setup-panel">
          {/* Goal Input */}
          <div className="goal-section">
            <label htmlFor="goal">Negotiation Goal</label>
            <textarea
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Enter the objective both agents must work toward...&#10;&#10;Example: Agree on a fair price for the used car that satisfies both buyer and seller."
              disabled={isNegotiating}
              rows={3}
            />
          </div>

          {/* Agent Info Split */}
          <div className="agents-split">
            <div className="agent-panel agent-a">
              <div className="agent-header">
                <span className="agent-icon">A</span>
                <span className="agent-label">Agent A - Private Information</span>
              </div>
              <textarea
                value={agentAInfo}
                onChange={(e) => setAgentAInfo(e.target.value)}
                placeholder="Enter Agent A's private constraints and context...&#10;&#10;Example:&#10;You are the buyer.&#10;- Maximum budget: $15,000&#10;- You noticed scratches on the car&#10;- You need the car urgently"
                disabled={isNegotiating}
                rows={6}
              />
            </div>

            <div className="agent-panel agent-b">
              <div className="agent-header">
                <span className="agent-icon">B</span>
                <span className="agent-label">Agent B - Private Information</span>
              </div>
              <textarea
                value={agentBInfo}
                onChange={(e) => setAgentBInfo(e.target.value)}
                placeholder="Enter Agent B's private constraints and context...&#10;&#10;Example:&#10;You are the seller.&#10;- Minimum acceptable price: $12,000&#10;- You recently did expensive maintenance&#10;- You're in no rush to sell"
                disabled={isNegotiating}
                rows={6}
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="action-buttons">
            <button
              className="start-btn"
              onClick={startNegotiation}
              disabled={isNegotiating || !goal.trim() || !agentAInfo.trim() || !agentBInfo.trim()}
            >
              {isNegotiating ? 'Negotiating...' : 'Start Negotiation'}
            </button>
            {(turns.length > 0 || status) && (
              <button
                className="reset-btn"
                onClick={resetNegotiation}
                disabled={isNegotiating}
              >
                Reset
              </button>
            )}
          </div>
        </section>

        {/* Negotiation Transcript */}
        {(turns.length > 0 || isNegotiating) && (
          <section className="transcript-section">
            <h2>Negotiation Transcript</h2>

            <div className="transcript-container">
              {turns.map((turn, idx) => (
                <TurnCard key={idx} turn={turn} />
              ))}

              {isNegotiating && status === 'in_progress' && (
                <div className="loading-turn">
                  <div className="loading-spinner" />
                  <span>Turn {currentTurn + 1} in progress...</span>
                </div>
              )}

              <div ref={transcriptEndRef} />
            </div>
          </section>
        )}

        {/* Final Outcome */}
        {finalConclusion && (
          <section className={`outcome-section ${status}`}>
            <h2>
              {status === 'consensus' ? 'Agreement Reached' : 'Negotiation Ended'}
            </h2>
            <div className="outcome-content">
              <p>{finalConclusion}</p>
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>Multi-Agent Negotiation System - Powered by Claude</p>
      </footer>
    </div>
  )
}

function TurnCard({ turn }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="turn-card">
      <div className="turn-header">
        <span className="turn-number">Turn {turn.turn}</span>
        <div className="progress-indicator">
          <span className="progress-label">Progress:</span>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(turn.progressScore || 0) * 10}%` }}
            />
          </div>
          <span className="progress-value">{turn.progressScore || 0}/10</span>
        </div>
      </div>

      <div className="turn-content">
        <div className="agent-message agent-a-msg">
          <div className="message-header">
            <span className="agent-badge a">A</span>
            <span>Agent A</span>
          </div>
          <p>{turn.agentA}</p>
        </div>

        <div className="agent-message agent-b-msg">
          <div className="message-header">
            <span className="agent-badge b">B</span>
            <span>Agent B</span>
          </div>
          <p>{turn.agentB}</p>
        </div>
      </div>

      {turn.judge && (
        <div className="judge-section">
          <div
            className="judge-header"
            onClick={() => setExpanded(!expanded)}
          >
            <span className="judge-icon">Judge</span>
            <span className={`judge-verdict ${turn.judge.progress ? 'progress' : 'no-progress'}`}>
              {turn.judge.is_consensus
                ? 'Consensus Detected'
                : turn.judge.is_deadlock
                ? 'Deadlock Detected'
                : turn.judge.progress
                ? 'Making Progress'
                : 'No Progress'}
            </span>
            <span className="expand-icon">{expanded ? '[-]' : '[+]'}</span>
          </div>

          {expanded && (
            <div className="judge-reasoning">
              <p>{turn.judge.reasoning}</p>
              {turn.judge.consensus_summary && (
                <div className="consensus-summary">
                  <strong>Summary:</strong> {turn.judge.consensus_summary}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
