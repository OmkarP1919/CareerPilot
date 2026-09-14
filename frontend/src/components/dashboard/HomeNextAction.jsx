import { Link } from "react-router-dom";
import { Sparkles, Upload, Calendar, Compass, ArrowRight, RefreshCw } from "lucide-react";

export default function HomeNextAction({ action }) {
  if (!action) return null;

  const renderIcon = () => {
    switch (action.ctaIcon) {
      case "upload":
        return <Upload size={18} aria-hidden="true" />;
      case "calendar":
        return <Calendar size={18} aria-hidden="true" />;
      case "sparkles":
        return <Sparkles size={18} aria-hidden="true" />;
      case "refresh":
        return <RefreshCw size={18} aria-hidden="true" />;
      default:
        return <Compass size={18} aria-hidden="true" />;
    }
  };

  return (
    <section className="home-next-step-section" aria-labelledby="home-next-step-title">
      <div className={`card home-next-step-card variant-${action.variant || "neutral"}`}>
        <div className="home-next-step-inner">
          <div className="home-next-step-body">
            <span className="home-next-step-eyebrow">{action.eyebrow}</span>
            <h2 id="home-next-step-title" className="home-next-step-title">
              {action.title}
            </h2>
            <p className="home-next-step-desc">{action.description}</p>
          </div>

          <div className="home-next-step-actions">
            <Link
              to={action.ctaLink}
              state={action.ctaState}
              className="btn btn-primary home-next-step-primary-btn"
            >
              {renderIcon()}
              <span>{action.ctaLabel}</span>
            </Link>

            {action.secondaryLabel && action.secondaryLink && (
              <Link
                to={action.secondaryLink}
                className="btn btn-secondary home-next-step-secondary-btn"
              >
                <span>{action.secondaryLabel}</span>
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
