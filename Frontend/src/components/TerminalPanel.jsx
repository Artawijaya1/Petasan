export function TerminalPanel({ isRunning, terminalOutput }) {
  return (
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
  )
}
