export function ActivityPanel({ events }) {
  return (
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
  )
}
