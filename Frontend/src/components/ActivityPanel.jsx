export function ActivityPanel({ events }) {
  return (
    <section className="activity-panel" aria-labelledby="activity-title">
      <div className="section-heading activity-heading">
        <span className="section-index">02</span>
        <div>
          <h2 id="activity-title">Agent Activity</h2>
          <p>Events received directly from backend.</p>
        </div>
        <span className="event-count">{events.length.toString().padStart(2, '0')}</span>
      </div>

      {events.length === 0 ? (
        <div className="empty-activity">
          <span className="empty-mark" aria-hidden="true">—</span>
          <p>No activity yet</p>
        </div>
      ) : (
        <ol className="event-list" aria-live="polite">
          {[...events].reverse().map((event) => (
            <li className="event-item" key={event.id}>
              <span className={`event-mark ${event.status || event.type}`} aria-hidden="true" />
              <div>
                <div className="event-title-row">
                  <h3>{event.title || (event.type === 'agent_error' ? 'Request rejected' : 'Agent activity')}</h3>
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
