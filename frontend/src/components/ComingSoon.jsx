export default function ComingSoon({ feature }) {
  return (
    <div className="coming-soon">
      <div className="coming-soon-content">
        <span className="coming-soon-icon">🚀</span>
        <h2>{feature || "This Feature"}</h2>
        <p>Coming Soon</p>
      </div>
    </div>
  );
}
