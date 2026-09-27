export function Header({ connectionState, connectionLabel, onReconnect }) {
  return (
    <header className="topbar">
      <a className="brand" href="#top" aria-label="Zeto dashboard">
        <span className="brand-mark" aria-hidden="true">Z</span>
        <span>ZETO <small>AGENT CONSOLE</small></span>
      </a>
      <div className="topbar-status">
        <span className={`status-dot ${connectionState}`} />
        <span>{connectionLabel}</span>
        {connectionState !== 'connected' && (
          <button
            className="text-button"
            type="button"
            onClick={onReconnect}
          >
            Reconnect
          </button>
        )}
      </div>
    </header>
  )
}
