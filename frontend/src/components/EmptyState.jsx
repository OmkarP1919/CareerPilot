export default function EmptyState({ icon: Icon, title, description, text, action, children }) {
  const desc = description || text;
  return (
    <div className="empty-state">
      {Icon && (
        <div className="empty-state-icon">
          <Icon size={24} />
        </div>
      )}
      {title && <h3>{title}</h3>}
      {desc && <p>{desc}</p>}
      {action || children}
    </div>
  );
}
