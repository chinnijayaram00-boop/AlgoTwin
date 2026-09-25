export function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

export function LoadingState({ label = "Loading workspace" }) {
  return (
    <div className="feedback-state" role="status">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="feedback-state error-state" role="alert">
      <span className="feedback-icon">!</span>
      <div>
        <strong>Something needs attention</strong>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button className="button button-quiet" onClick={onRetry} type="button">
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="empty-state">
      <div className="empty-orb" />
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </div>
  );
}

export function SectionCard({ title, description, children, className = "" }) {
  return (
    <section className={`section-card ${className}`}>
      {title ? (
        <div className="section-card-header">
          <div>
            <h3>{title}</h3>
            {description ? <p>{description}</p> : null}
          </div>
        </div>
      ) : null}
      {children}
    </section>
  );
}
