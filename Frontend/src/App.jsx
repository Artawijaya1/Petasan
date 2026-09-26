import { useEffect, useRef, useState } from 'react'
import './App.css'

const backendPort = import.meta.env.VITE_BACKEND_PORT || '8000'
const backendUrl = import.meta.env.VITE_BACKEND_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:${backendPort}/ws/agent`

const initialTerminal = 'PETASAN // agent terminal\nMenunggu permintaan...\n'

function App() {
  const [connectionState, setConnectionState] = useState('connecting')
  const [repoPath, setRepoPath] = useState('')
  const [trusted, setTrusted] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [runStatus, setRunStatus] = useState('idle')
  const [events, setEvents] = useState([])
  const [terminalOutput, setTerminalOutput] = useState(initialTerminal)
  const [reconnectKey, setReconnectKey] = useState(0)
  const socketRef = useRef(null)
  const eventId = useRef(0)

  useEffect(() => {
    const socket = new WebSocket(backendUrl)
    socketRef.current = socket

    socket.addEventListener('open', () => setConnectionState('connected'))
    socket.addEventListener('message', (message) => {
      let event
      try {
        event = JSON.parse(message.data)
      } catch {
        setTerminalOutput((output) => `${output}\nRespons backend tidak valid.\n`)
        return
      }

      if (event.type === 'terminal_log') {
        setTerminalOutput((output) => `${output}${event.content || ''}`.slice(-24000))
        return
      }

      if (event.type === 'agent_thought' || event.type === 'agent_error') {
        setEvents((current) => [
          ...current,
          { ...event, id: eventId.current++ },
        ].slice(-80))
        if (event.status === 'failed' || event.type === 'agent_error') {
          setRunStatus('failed')
        }
        if (event.type === 'agent_error') setIsRunning(false)
        return
      }

      if (event.type === 'agent_finished' || event.type === 'agent_complete') {
        setIsRunning(false)
        setRunStatus(event.status === 'completed' ? 'completed' : 'failed')
      }
    })
    socket.addEventListener('error', () => setConnectionState('error'))
    socket.addEventListener('close', () => {
      setConnectionState('disconnected')
      setIsRunning(false)
      setRunStatus((status) => status === 'running' ? 'failed' : status)
      if (socketRef.current === socket) socketRef.current = null
    })

    return () => {
      socket.close()
      if (socketRef.current === socket) socketRef.current = null
    }
  }, [reconnectKey])

  function startProvisioning(event) {
    event.preventDefault()
    const socket = socketRef.current
    if (!repoPath.trim() || !trusted || socket?.readyState !== WebSocket.OPEN) return

    setEvents([])
    setTerminalOutput(`PETASAN // ${repoPath.trim()}\nMemulai sesi agent...\n`)
    setIsRunning(true)
    setRunStatus('running')
    socket.send(JSON.stringify({ action: 'start', repo_path: repoPath.trim() }))
  }

  const connectionLabel = {
    connecting: 'Menyambungkan',
    connected: 'Backend terhubung',
    disconnected: 'Backend terputus',
    error: 'Koneksi bermasalah',
  }[connectionState]

  const runLabel = {
    idle: 'Belum dijalankan',
    running: 'Sedang berjalan',
    completed: 'Selesai',
    failed: 'Perlu perhatian',
  }[runStatus]

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Petasan dashboard">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>PETASAN <small>AGENT CONSOLE</small></span>
        </a>
        <div className="topbar-status">
          <span className={`status-dot ${connectionState}`} />
          <span>{connectionLabel}</span>
          {connectionState !== 'connected' && (
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setConnectionState('connecting')
                setReconnectKey((key) => key + 1)
              }}
            >
              Sambungkan ulang
            </button>
          )}
        </div>
      </header>

      <main id="top">
        <section className="intro">
          <div>
            <p className="eyebrow">ORKESTRASI LINGKUNGAN PROYEK</p>
            <h1>Siapkan proyek.<br /><span>Pantau setiap langkah.</span></h1>
          </div>
          <p className="intro-note">Gateway <code>{backendUrl}</code></p>
        </section>

        <section className="workspace" aria-label="Kontrol agent dan aktivitas">
          <div className="control-panel">
            <div className="section-heading">
              <span className="section-index">01</span>
              <div>
                <h2>Mulai sesi</h2>
                <p>Target harus dapat diakses oleh mesin backend.</p>
              </div>
            </div>

            <form onSubmit={startProvisioning}>
              <label htmlFor="repo-path">Path direktori proyek</label>
              <input
                id="repo-path"
                name="repoPath"
                type="text"
                autoComplete="off"
                spellCheck="false"
                placeholder="D:\\projects\\my-app"
                value={repoPath}
                onChange={(event) => setRepoPath(event.target.value)}
                disabled={isRunning}
              />
              <p className="field-hint">Path lokal pada komputer/server yang menjalankan Backend.</p>

              <label className="trust-check">
                <input
                  type="checkbox"
                  checked={trusted}
                  onChange={(event) => setTrusted(event.target.checked)}
                  disabled={isRunning}
                />
                <span>Saya mempercayai proyek ini dan mengizinkan perintah dijalankan.</span>
              </label>

              <button
                className="run-button"
                type="submit"
                disabled={connectionState !== 'connected' || isRunning || !repoPath.trim() || !trusted}
              >
                <span aria-hidden="true">{isRunning ? '■' : '▶'}</span>
                {isRunning ? 'Agent sedang bekerja' : 'Jalankan agent'}
              </button>
            </form>

            <div className="run-summary">
              <span className={`status-dot run-${runStatus}`} />
              <span>Sesi</span>
              <strong>{runLabel}</strong>
            </div>
          </div>

          <section className="activity-panel" aria-labelledby="activity-title">
            <div className="section-heading activity-heading">
              <span className="section-index">02</span>
              <div>
                <h2 id="activity-title">Aktivitas agent</h2>
                <p>Peristiwa diterima langsung dari backend.</p>
              </div>
              <span className="event-count">{events.length.toString().padStart(2, '0')}</span>
            </div>

            {events.length === 0 ? (
              <div className="empty-activity">
                <span className="empty-mark" aria-hidden="true">—</span>
                <p>Belum ada aktivitas</p>
              </div>
            ) : (
              <ol className="event-list" aria-live="polite">
                {[...events].reverse().map((event) => (
                  <li className="event-item" key={event.id}>
                    <span className={`event-mark ${event.status || event.type}`} aria-hidden="true" />
                    <div>
                      <div className="event-title-row">
                        <h3>{event.title || (event.type === 'agent_error' ? 'Permintaan ditolak' : 'Aktivitas agent')}</h3>
                        {event.status && <span className={`event-status ${event.status}`}>{event.status}</span>}
                      </div>
                      <p>{event.content}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </section>

        <section className="terminal-panel" aria-labelledby="terminal-title">
          <div className="terminal-heading">
            <div>
              <span className="section-index">03</span>
              <h2 id="terminal-title">Terminal</h2>
            </div>
            <span className={`terminal-live ${isRunning ? 'active' : ''}`}>
              <span className="status-dot" />{isRunning ? 'LIVE' : 'STREAM'}
            </span>
          </div>
          <pre className="terminal-output" aria-live="polite">{terminalOutput}</pre>
        </section>
      </main>

      <footer className="footer">
        <span>PETASAN <span className="footer-divider">/</span> LOCAL AGENT WORKSPACE</span>
        <span>WEBSOCKET <code>/ws/agent</code></span>
      </footer>
    </div>
  )
}

export default App
