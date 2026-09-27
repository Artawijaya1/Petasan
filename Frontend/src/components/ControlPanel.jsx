export function ControlPanel({
  repoPath,
  setRepoPath,
  trusted,
  setTrusted,
  isRunning,
  runStatus,
  runLabel,
  connectionState,
  onSubmit,
}) {
  return (
    <div className="control-panel">
      <div className="section-heading">
        <span className="section-index">01</span>
        <div>
          <h2>Start Session</h2>
          <p>Target must be accessible by the backend machine.</p>
        </div>
      </div>

      <form onSubmit={onSubmit}>
        <label htmlFor="repo-path">Project directory path</label>
        <input
          id="repo-path"
          name="repoPath"
          type="text"
          autoComplete="off"
          spellCheck="false"
          placeholder="D:\projects\my-app"
          value={repoPath}
          onChange={(event) => setRepoPath(event.target.value)}
          disabled={isRunning}
        />
        <p className="field-hint">Local path on the computer/server running the Backend.</p>

        <label className="trust-check">
          <input
            type="checkbox"
            checked={trusted}
            onChange={(event) => setTrusted(event.target.checked)}
            disabled={isRunning}
          />
          <span>I trust this project and authorize command execution.</span>
        </label>

        <button
          className="run-button"
          type="submit"
          disabled={connectionState !== 'connected' || isRunning || !repoPath.trim() || !trusted}
        >
          <span aria-hidden="true">{isRunning ? '■' : '▶'}</span>
          {isRunning ? 'Agent working' : 'Run agent'}
        </button>
      </form>

      <div className="run-summary">
        <span className={"status-dot run-" + runStatus} />
        <span>Session</span>
        <strong>{runLabel}</strong>
      </div>
    </div>
  )
}