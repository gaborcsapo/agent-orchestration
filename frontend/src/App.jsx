import { useState, useEffect, useRef } from 'react'

const API_BASE = '/api'

function App() {
  const [conversations, setConversations] = useState([])
  const [currentConversation, setCurrentConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  const messagesEndRef = useRef(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Check health on mount
  useEffect(() => {
    checkHealth()
    loadConversations()
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

  const loadConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`)
      if (res.ok) {
        const data = await res.json()
        setConversations(data.conversations || [])
      }
    } catch (e) {
      console.error('Failed to load conversations:', e)
    }
  }

  const loadConversation = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/conversations/${id}`)
      if (res.ok) {
        const data = await res.json()
        setCurrentConversation(data.conversation)
        setMessages(data.messages || [])
      }
    } catch (e) {
      console.error('Failed to load conversation:', e)
    }
  }

  const startNewConversation = () => {
    setCurrentConversation(null)
    setMessages([])
    setError(null)
  }

  const deleteConversation = async (id, e) => {
    e.stopPropagation()
    try {
      await fetch(`${API_BASE}/conversations/${id}`, { method: 'DELETE' })
      setConversations(conversations.filter(c => c.id !== id))
      if (currentConversation?.id === id) {
        startNewConversation()
      }
    } catch (e) {
      console.error('Failed to delete conversation:', e)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setError(null)
    setLoading(true)

    // Add user message to UI immediately
    const tempUserMsg = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: userMessage,
    }
    setMessages(prev => [...prev, tempUserMsg])

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: currentConversation?.id || null,
        }),
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Chat request failed')
      }

      const data = await res.json()

      // Update conversation ID if new
      if (!currentConversation) {
        setCurrentConversation({ id: data.conversation_id, title: userMessage.slice(0, 50) })
        loadConversations()
      }

      // Add assistant message
      const assistantMsg = {
        id: 'msg-' + Date.now(),
        role: 'assistant',
        content: data.response,
        agent_steps: data.agent_steps,
      }
      setMessages(prev => [...prev, assistantMsg])

    } catch (e) {
      setError(e.message)
      // Remove the temporary user message on error
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id))
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Agent Orchestration</h1>
          <p>LangGraph + LangChain + MongoDB</p>
        </div>

        <button className="new-chat-btn" onClick={startNewConversation}>
          + New Chat
        </button>

        <div className="conversations-list">
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`conversation-item ${currentConversation?.id === conv.id ? 'active' : ''}`}
              onClick={() => loadConversation(conv.id)}
            >
              <span className="conversation-title">{conv.title}</span>
              <button
                className="delete-btn"
                onClick={(e) => deleteConversation(conv.id, e)}
              >
                x
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-main">
        <header className="chat-header">
          <h2>{currentConversation?.title || 'New Conversation'}</h2>
          <div className="status-indicator">
            <span className={`status-dot ${health?.status === 'healthy' ? '' : health?.status === 'error' ? 'error' : 'loading'}`} />
            <span>
              {health?.status === 'healthy' ? 'Connected' :
               health?.status === 'error' ? 'Disconnected' : 'Checking...'}
            </span>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <h3>Start a Conversation</h3>
              <p>
                This multi-agent system uses a Research Agent to analyze your query
                and a Writer Agent to synthesize a comprehensive response.
              </p>
            </div>
          ) : (
            messages.map(msg => (
              <Message key={msg.id} message={msg} />
            ))
          )}

          {loading && (
            <div className="loading-indicator">
              <div className="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span>Agents are working...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <div className="input-wrapper">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={loading}
              rows={1}
            />
            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

function Message({ message }) {
  const [showSteps, setShowSteps] = useState(false)

  return (
    <div className={`message ${message.role}`}>
      <div className="message-role">
        {message.role === 'user' ? 'You' : 'Assistant'}
      </div>
      <div className="message-content">
        {message.content}
      </div>

      {message.agent_steps?.length > 0 && (
        <div className="agent-steps">
          <div
            className="agent-steps-header"
            onClick={() => setShowSteps(!showSteps)}
          >
            {showSteps ? '[-]' : '[+]'} View agent steps ({message.agent_steps.length})
          </div>

          {showSteps && message.agent_steps.map((step, idx) => (
            <div key={idx} className="agent-step">
              <div className="agent-step-name">
                {step.agent?.toUpperCase() || 'AGENT'} Agent
              </div>
              <div className="agent-step-output">
                {step.output?.slice(0, 300)}
                {step.output?.length > 300 && '...'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
