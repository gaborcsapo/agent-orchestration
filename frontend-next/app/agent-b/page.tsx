'use client'

import { useState, useEffect, useRef } from 'react'
import { agentBApi, arenaApi, type AuditEntry, type TurnData } from '@/lib/api'

export default function AgentBPage() {
  // Form state
  const [sessionId, setSessionId] = useState('')
  const [privateInfo, setPrivateInfo] = useState('')

  // Session state
  const [joined, setJoined] = useState(false)
  const [auditTrail, setAuditTrail] = useState<AuditEntry[]>([])
  const [publicTurns, setPublicTurns] = useState<TurnData[]>([])
  const [sessionStatus, setSessionStatus] = useState<string | null>(null)
  const [finalConclusion, setFinalConclusion] = useState<string | null>(null)

  // UI state
  const [isJoining, setIsJoining] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedTurns, setExpandedTurns] = useState<Set<number>>(new Set())

  const transcriptRef = useRef<HTMLDivElement>(null)

  // Default private info for demo
  const defaultPrivateInfo = `I'm Jordan, and I want us to build a substantial family trust fund. Here are my constraints:

- My monthly income is $12,000 after taxes
- I have no significant debt payments
- I believe we should each contribute fairly based on our ability
- I think the trust should receive at least $5,000/month total to be meaningful
- Ideally, I'd like Alex to contribute around $3,000-4,000/month
- My walk-away point (BATNA): If Alex won't commit to at least $2,500/month, I'd rather invest in my own retirement account instead

I suspect Alex has student loans but I don't know the exact amount. I don't want to reveal how much I think they should contribute or my minimum expectations.`

  // Poll for updates when joined
  useEffect(() => {
    if (!joined || !sessionId) return

    const interval = setInterval(async () => {
      try {
        // Get audit trail
        const auditData = await agentBApi.getAudit(sessionId)
        setAuditTrail(auditData.audit_trail)

        // Get public conversation
        const history = await arenaApi.getHistory(sessionId)
        setPublicTurns(history.turns)
        setSessionStatus(history.status)
        if (history.final_conclusion) {
          setFinalConclusion(history.final_conclusion)
        }

        // Auto-expand new turns
        if (auditData.audit_trail.length > expandedTurns.size) {
          const newTurns = new Set(expandedTurns)
          auditData.audit_trail.forEach(entry => newTurns.add(entry.turn))
          setExpandedTurns(newTurns)
        }
      } catch (err) {
        console.error('Error polling:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [joined, sessionId, expandedTurns.size])

  // Auto-scroll
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [auditTrail])

  // Join session
  const handleJoin = async () => {
    if (!sessionId.trim() || !privateInfo.trim()) return

    setIsJoining(true)
    setError(null)

    try {
      await agentBApi.join(sessionId, privateInfo)
      setJoined(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join session')
    } finally {
      setIsJoining(false)
    }
  }

  // Toggle turn expansion
  const toggleTurn = (turn: number) => {
    const newExpanded = new Set(expandedTurns)
    if (newExpanded.has(turn)) {
      newExpanded.delete(turn)
    } else {
      newExpanded.add(turn)
    }
    setExpandedTurns(newExpanded)
  }

  const isComplete = sessionStatus === 'consensus' || sessionStatus === 'deadlock'

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Partner B - Jordan
          </h1>
          <p className="page-subtitle">Private view - sees your thinking & strategy</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {sessionStatus && (
            <span className={`badge badge-${sessionStatus}`}>
              {sessionStatus.replace('_', ' ')}
            </span>
          )}
          <span className="agent-badge agent-badge-b">Agent B</span>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Join Form */}
      {!joined && (
        <div className="card">
          <h2 className="card-title">Join Negotiation as Partner B (Jordan)</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
            Enter the session ID from the Arena and your private financial information.
            This information stays on your server and is never shared with Partner A.
          </p>

          <div style={{ marginBottom: '1.5rem' }}>
            <label className="input-label">Session ID</label>
            <input
              type="text"
              className="input"
              placeholder="Enter session ID from Arena"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label className="input-label">
              Your Private Information
              <span style={{ color: 'var(--text-muted)', fontWeight: 'normal', marginLeft: '0.5rem' }}>
                (only you and your AI agent see this)
              </span>
            </label>
            <textarea
              className="textarea"
              placeholder="Enter your private constraints, expectations, walk-away point..."
              value={privateInfo}
              onChange={(e) => setPrivateInfo(e.target.value)}
              rows={10}
              style={{ fontFamily: 'inherit' }}
            />
            <button
              style={{
                marginTop: '0.5rem',
                padding: '0.5rem 1rem',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '0.875rem'
              }}
              onClick={() => setPrivateInfo(defaultPrivateInfo)}
            >
              Load Demo Scenario
            </button>
          </div>

          <div style={{
            padding: '1rem',
            background: 'var(--agent-b-bg)',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            borderLeft: '3px solid var(--agent-b)'
          }}>
            <strong style={{ color: 'var(--agent-b)' }}>Privacy Guarantee:</strong>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
              Your private information is processed only on Agent B's server. It physically cannot
              reach Partner A because it never leaves this backend service.
            </p>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleJoin}
            disabled={!sessionId.trim() || !privateInfo.trim() || isJoining}
            style={{ background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' }}
          >
            {isJoining ? (
              <>
                <span className="spinner" />
                Joining...
              </>
            ) : (
              'Join as Partner B'
            )}
          </button>
        </div>
      )}

      {/* Joined View */}
      {joined && (
        <>
          {/* Session info */}
          <div className="session-info">
            <div>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Session:</span>
              <div className="session-id" style={{ color: 'var(--agent-b)' }}>{sessionId}</div>
            </div>
            <span className="agent-badge agent-badge-b">You are Jordan (Partner B)</span>
          </div>

          {/* Waiting state */}
          {auditTrail.length === 0 && !isComplete && (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              <div className="spinner" style={{ margin: '0 auto 1rem' }} />
              <h3>Waiting for Negotiation to Start</h3>
              <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                Your private information has been securely stored. The negotiation will begin
                once Partner A joins and the Arena starts the session.
              </p>
            </div>
          )}

          {/* Audit Trail */}
          {auditTrail.length > 0 && (
            <div ref={transcriptRef} style={{ maxHeight: '800px', overflowY: 'auto' }}>
              <h2 style={{ marginBottom: '1rem' }}>Your Private Thinking Process</h2>

              {auditTrail.map((entry, idx) => {
                const publicTurn = publicTurns.find(t => t.turn === entry.turn)
                const isExpanded = expandedTurns.has(entry.turn)

                return (
                  <div key={idx} className="turn-card">
                    <div
                      className="turn-header"
                      onClick={() => toggleTurn(entry.turn)}
                      style={{ cursor: 'pointer' }}
                    >
                      <div className="turn-number">
                        <span style={{
                          background: 'var(--agent-b)',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '4px',
                          fontSize: '0.875rem',
                          color: 'white'
                        }}>
                          Turn {entry.turn}
                        </span>
                        <span className="strategy-badge" style={{ background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' }}>
                          {entry.strategy}
                        </span>
                      </div>
                      <span style={{ color: 'var(--text-muted)' }}>
                        {isExpanded ? '▼' : '▶'}
                      </span>
                    </div>

                    {isExpanded && (
                      <div className="turn-content">
                        {/* Partner A's message */}
                        {publicTurn && (
                          <div className="message-block message-block-a">
                            <div className="message-sender" style={{ color: 'var(--agent-a)' }}>
                              Alex's Message (Partner A)
                            </div>
                            <div className="message-text">{publicTurn.agent_a_message}</div>
                          </div>
                        )}

                        {/* Your public message */}
                        <div className="message-block message-block-b">
                          <div className="message-sender" style={{ color: 'var(--agent-b)' }}>
                            What You Said (Public)
                          </div>
                          <div className="message-text">{entry.final_message}</div>
                        </div>

                        {/* BATNA Analysis */}
                        <div className="batna-section" style={{ borderLeftColor: 'var(--agent-b)' }}>
                          <div className="batna-header" style={{ color: 'var(--agent-b)' }}>
                            BATNA Analysis (Walk-Away Point)
                          </div>
                          {entry.batna_analysis.batna_value && (
                            <div className="batna-value">
                              ${entry.batna_analysis.batna_value.toLocaleString()}/month
                            </div>
                          )}
                          <div className="batna-description">
                            {entry.batna_analysis.batna_description}
                          </div>
                          <div style={{
                            marginTop: '0.5rem',
                            fontSize: '0.875rem',
                            color: entry.batna_analysis.current_offer_acceptable ? 'var(--consensus)' : 'var(--deadlock)'
                          }}>
                            {entry.batna_analysis.current_offer_acceptable
                              ? '✓ Current negotiation state is acceptable'
                              : '✗ Current offer would be below BATNA'}
                          </div>
                        </div>

                        {/* Thinking Steps */}
                        <div className="thinking-section">
                          <div className="thinking-header">
                            🧠 Your Private Thinking
                          </div>
                          {entry.thinking_steps.map((step, stepIdx) => (
                            <div key={stepIdx} className="thinking-step">
                              <div className="thinking-step-number" style={{ background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' }}>
                                {stepIdx + 1}
                              </div>
                              <div className="thinking-step-text">{step}</div>
                            </div>
                          ))}
                        </div>

                        {/* CI Gateway */}
                        <div className="ci-section">
                          <div className="ci-header">
                            🛡️ Contextual Integrity Gateway
                          </div>
                          {entry.ci_gateway_log.decisions.map((decision, decIdx) => (
                            <div key={decIdx} className="ci-decision">
                              <div className="ci-decision-header">
                                <span className={`ci-badge ci-badge-${decision.action.toLowerCase()}`}>
                                  {decision.action}
                                </span>
                                <span className="ci-decision-text">{decision.reason}</span>
                              </div>
                              {decision.action !== 'ALLOW' && (
                                <div className="ci-decision-text">
                                  <span className="ci-decision-original">
                                    Original: "{decision.original}"
                                  </span>
                                  {decision.result && (
                                    <span className="ci-decision-result">
                                      {' → '} "{decision.result}"
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                          {entry.ci_gateway_log.original_message !== entry.ci_gateway_log.filtered_message && (
                            <div style={{
                              marginTop: '1rem',
                              padding: '0.75rem',
                              background: 'var(--bg-secondary)',
                              borderRadius: '6px',
                              fontSize: '0.875rem'
                            }}>
                              <div style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Message was modified by CI Gateway
                              </div>
                              <div style={{ color: 'var(--ci-block)', textDecoration: 'line-through' }}>
                                {entry.ci_gateway_log.original_message}
                              </div>
                              <div style={{ color: 'var(--ci-allow)', marginTop: '0.5rem' }}>
                                {entry.ci_gateway_log.filtered_message}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Outcome */}
          {isComplete && finalConclusion && (
            <div className={`outcome-section ${sessionStatus === 'consensus' ? 'outcome-consensus' : 'outcome-deadlock'}`}>
              <div className="outcome-title">
                {sessionStatus === 'consensus' ? '🤝 Agreement Reached!' : '⚠️ Negotiation Ended'}
              </div>
              <div className="outcome-text">{finalConclusion}</div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
