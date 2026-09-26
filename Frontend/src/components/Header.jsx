export function Header({ connectionState, connectionLabel, onReconnect }) {
  return (
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
            onClick={onReconnect}
          >
            Sambungkan ulang
          </button>
        )}
      </div>
    </header>
  )
}
