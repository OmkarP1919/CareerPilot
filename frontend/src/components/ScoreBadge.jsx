import { getMatchLabel, getMatchClass } from "../utils/constants";

export default function ScoreBadge({ score, size = "default" }) {
  const label = getMatchLabel(score);
  const className = getMatchClass(score);

  if (size === "large") {
    return (
      <div className={`match-score-circle ${className}`} role="img" aria-label={`Match score: ${score}%, ${label}`}>
        <span className="score-value">{score}%</span>
        <span className="score-label">{label}</span>
      </div>
    );
  }

  return (
    <span className={`match-score-badge ${className}`} role="status" aria-label={`Match score: ${score}%, ${label}`}>
      {score}% {label}
    </span>
  );
}
