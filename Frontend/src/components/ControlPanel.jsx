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
          <h2>Mulai sesi</h2>
          <p>Target harus dapat diakses oleh mesin backend.</p>
        </div>
      </div>

      <form onSubmit={onSubmit}>
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
  )
}
