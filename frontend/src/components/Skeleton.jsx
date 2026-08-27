export function SkeletonCard({ lines = 3, className = "" }) {
  return (
    <div className={`skeleton-card ${className}`}>
      <div className="skeleton skeleton-title" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton skeleton-text" style={i === lines - 1 ? { width: "60%" } : undefined} />
      ))}
    </div>
  );
}

export function SkeletonList({ count = 3 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} lines={2} />
      ))}
    </div>
  );
}

export function SkeletonStats({ count = 4 }) {
  return (
    <div className="stats-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card" style={{ padding: "var(--space-5)" }}>
          <div className="skeleton skeleton-circle" style={{ width: 40, height: 40, marginBottom: "var(--space-3)" }} />
          <div className="skeleton skeleton-title" style={{ width: "30%" }} />
          <div className="skeleton skeleton-text" style={{ width: "50%" }} />
        </div>
      ))}
    </div>
  );
}
