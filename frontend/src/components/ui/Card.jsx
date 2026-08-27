export default function Card({ header, footer, children, className = "", hover = false }) {
  return (
    <div className={`card ${hover ? "card-hover" : ""} ${className}`}>
      {header && <div className="card-header">{header}</div>}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
}

export function CardHeader({ children, action }) {
  return (
    <div className="card-header">
      {children}
      {action}
    </div>
  );
}
