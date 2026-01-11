'use client'

import { useState, useEffect, useRef } from 'react'
import { arenaApi, type TurnData, type SessionStatus } from '@/lib/api'

export default function ArenaPage() {
  // Form state
  const [goal, setGoal] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Session state
  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [turns, setTurns] = useState<TurnData[]>([])
  const [finalConclusion, setFinalConclusion] = useState<string | null>(null)

  // UI state
  const [isCreating, setIsCreating] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<{ status: string; services: Record<string, string> } | null>(null)

  const eventSourceRef = useRef<EventSource | null>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)

  // Check health on mount
  useEffect(() => {
    arenaApi.health().then(setHealth).catch(console.error)
  }, [])

  // Auto-scroll to bottom when new turns arrive
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [turns])

  // Poll for status updates
  useEffect(() => {
    if (!sessionId) return

    const interval = setInterval(async () => {
      try {
        const s = await arenaApi.getStatus(sessionId)
        setStatus(s)
      } catch (err) {
        console.error('Error polling status:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [sessionId])

  // Create session
  const handleCreateSession = async () => {
    if (!goal.trim()) return

    setIsCreating(true)
    setError(null)

    try {
      const result = await arenaApi.createSession(goal)
      setSessionId(result.session_id)

      // Get initial status
      const s = await arenaApi.getStatus(result.session_id)
      setStatus(s)

      // Connect to SSE stream
      connectToStream(result.session_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session')
    } finally {
      setIsCreating(false)
    }
  }

  // Connect to SSE stream
  const connectToStream = (sid: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const es = arenaApi.streamEvents(sid)
    eventSourceRef.current = es

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'turn') {
          setTurns(prev => [...prev, {
            turn: data.turn,
            agent_a_message: data.agent_a_message,
            agent_b_message: data.agent_b_message,
            judge: data.judge
          }])
        } else if (data.type === 'complete') {
          setFinalConclusion(data.conclusion)
        } else if (data.type === 'status') {
          setStatus(prev => prev ? { ...prev, ...data } : null)
        }
      } catch (err) {
        console.error('Error parsing SSE event:', err)
      }
    }

    es.onerror = () => {
      console.error('SSE connection error')
    }
  }

  // Start negotiation
  const handleStartNegotiation = async () => {
    if (!sessionId) return

    setIsStarting(true)
    setError(null)

    try {
      await arenaApi.startNegotiation(sessionId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start negotiation')
    } finally {
      setIsStarting(false)
    }
  }

  // Reset
  const handleReset = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    setSessionId(null)
    setStatus(null)
    setTurns([])
    setFinalConclusion(null)
    setGoal('')
    setError(null)
  }

  // Copy session ID
  const copySessionId = () => {
    if (sessionId) {
      navigator.clipboard.writeText(sessionId)
    }
  }

  const canStart = status?.agent_a_ready && status?.agent_b_ready && status?.status === 'ready'
  const isComplete = status?.status === 'consensus' || status?.status === 'deadlock'

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Negotiation Arena</h1>
          <p className="page-subtitle">Public view - only sees shared messages</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {health && (
            <span className={`badge badge-${health.status === 'ok' ? 'consensus' : 'deadlock'}`}>
              {health.status === 'ok' ? 'All Services Online' : 'Some Services Offline'}
            </span>
          )}
          {status && (
            <span className={`badge badge-${status.status}`}>
              {status.status.replace('_', ' ')}
            </span>
          )}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Setup Panel - only show if no session */}
      {!sessionId && (
        <div className="card">
          <h2 className="card-title">Create Negotiation Session</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
            Set up a trust fund contribution negotiation between two partners.
          </p>

          <div style={{ marginBottom: '1.5rem' }}>
            <label className="input-label">Negotiation Goal</label>
            <textarea
              className="textarea"
              placeholder="e.g., Alex and Jordan need to agree on monthly contributions to their family trust fund. The goal is to find a fair split that works for both partners' financial situations."
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={4}
            />
          </div>

          <button
            className="btn btn-primary"
            onClick={handleCreateSession}
            disabled={!goal.trim() || isCreating}
          >
            {isCreating ? (
              <>
                <span className="spinner" />
                Creating...
              </>
            ) : (
              'Create Session'
            )}
          </button>
        </div>
      )}

      {/* Session Info - show after session created */}
      {sessionId && (
        <>
          <div className="session-info">
            <div>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Session ID:</span>
              <div className="session-id">{sessionId}</div>
            </div>
            <button className="copy-btn" onClick={copySessionId} title="Copy Session ID">
              📋
            </button>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <span className={`badge ${status?.agent_a_ready ? 'badge-consensus' : 'badge-waiting'}`}>
                {status?.agent_a_ready ? '✓' : '○'} Partner A
              </span>
              <span className={`badge ${status?.agent_b_ready ? 'badge-consensus' : 'badge-waiting'}`}>
                {status?.agent_b_ready ? '✓' : '○'} Partner B
              </span>
            </div>
          </div>

          {/* Goal display */}
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              Negotiation Goal:
            </div>
            <div style={{ fontSize: '1.125rem' }}>{goal}</div>
          </div>

          {/* Waiting message */}
          {status?.status === 'waiting' && (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⏳</div>
              <h3>Waiting for Partners to Join</h3>
              <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                Share the session ID with both partners. They should open their respective pages
                and enter their private information.
              </p>
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <a href="/agent-a" target="_blank" className="btn btn-secondary">
                  Open Partner A Page →
                </a>
                <a href="/agent-b" target="_blank" className="btn btn-secondary">
                  Open Partner B Page →
                </a>
              </div>
            </div>
          )}

          {/* Ready to start */}
          {status?.status === 'ready' && (
            <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
              <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>✅</div>
              <h3>Both Partners Ready!</h3>
              <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem', marginBottom: '1.5rem' }}>
                Click below to begin the negotiation.
              </p>
              <button
                className="btn btn-success"
                onClick={handleStartNegotiation}
                disabled={isStarting}
              >
                {isStarting ? (
                  <>
                    <span className="spinner" />
                    Starting...
                  </>
                ) : (
                  'Start Negotiation'
                )}
              </button>
            </div>
          )}

          {/* Transcript */}
          {(turns.length > 0 || status?.status === 'in_progress') && (
            <div>
              <h2 style={{ marginBottom: '1rem' }}>Public Conversation</h2>
              <div ref={transcriptRef} style={{ maxHeight: '600px', overflowY: 'auto' }}>
                {turns.map((turn, idx) => (
                  <div key={idx} className="turn-card">
                    <div className="turn-header">
                      <div className="turn-number">
                        <span style={{
                          background: 'var(--gradient-primary)',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '4px',
                          fontSize: '0.875rem'
                        }}>
                          Turn {turn.turn}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                          Progress:
                        </span>
                        <div className="progress-bar" style={{ width: '100px' }}>
                          <div
                            className="progress-fill"
                            style={{ width: `${turn.judge.progress_score * 10}%` }}
                          />
                        </div>
                        <span style={{ fontSize: '0.875rem', fontWeight: '600' }}>
                          {turn.judge.progress_score}/10
                        </span>
                      </div>
                    </div>
                    <div className="turn-content">
                      <div className="message-block message-block-a">
                        <div className="message-sender" style={{ color: 'var(--agent-a)' }}>
                          Alex (Partner A)
                        </div>
                        <div className="message-text">{turn.agent_a_message}</div>
                      </div>
                      <div className="message-block message-block-b">
                        <div className="message-sender" style={{ color: 'var(--agent-b)' }}>
                          Jordan (Partner B)
                        </div>
                        <div className="message-text">{turn.agent_b_message}</div>
                      </div>
                      <div className="message-block message-block-judge">
                        <div className="message-sender" style={{ color: 'var(--judge)' }}>
                          Judge Assessment
                        </div>
                        <div className="message-text">{turn.judge.reasoning}</div>
                        {turn.judge.is_consensus && turn.judge.consensus_summary && (
                          <div style={{
                            marginTop: '0.75rem',
                            padding: '0.75rem',
                            background: 'var(--consensus-bg)',
                            borderRadius: '6px',
                            color: 'var(--consensus)'
                          }}>
                            <strong>Agreement:</strong> {turn.judge.consensus_summary}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {status?.status === 'in_progress' && turns.length > 0 && (
                  <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
                    <div className="spinner" style={{ margin: '0 auto 1rem' }} />
                    <div style={{ color: 'var(--text-muted)' }}>
                      Processing turn {(turns.length || 0) + 1}...
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Outcome */}
          {isComplete && finalConclusion && (
            <div className={`outcome-section ${status?.status === 'consensus' ? 'outcome-consensus' : 'outcome-deadlock'}`}>
              <div className="outcome-title">
                {status?.status === 'consensus' ? '🤝 Agreement Reached!' : '⚠️ Negotiation Ended'}
              </div>
              <div className="outcome-text">{finalConclusion}</div>
            </div>
          )}

          {/* Reset button */}
          {isComplete && (
            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
              <button className="btn btn-secondary" onClick={handleReset}>
                Start New Negotiation
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
