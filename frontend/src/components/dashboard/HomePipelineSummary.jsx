import { Link } from "react-router-dom";
import { Layers, ArrowRight, Plus } from "lucide-react";
import { derivePipelineSummary } from "./dashboardUtils";

export default function HomePipelineSummary({ applications = [] }) {
  const summary = derivePipelineSummary(applications);

  // If no application activity yet, show simple invitation
  if (!summary || summary.total === 0) {
    return (
      <aside className="home-pipeline-card card empty" aria-label="Application tracking invitation">
        <div className="home-pipeline-content">
          <div className="home-pipeline-icon">
            <Layers size={18} aria-hidden="true" />
          </div>
          <div className="home-pipeline-text">
            <span className="home-pipeline-title">Application Pipeline</span>
            <span className="home-pipeline-desc">Start tracking your submissions and upcoming interviews</span>
          </div>
        </div>

        <Link to="/pipeline" className="btn btn-secondary btn-sm home-pipeline-action">
          <Plus size={14} aria-hidden="true" />
          <span>Track Application</span>
        </Link>
      </aside>
    );
  }

  return (
    <aside className="home-pipeline-card card" aria-label="Application pipeline snapshot">
      <div className="home-pipeline-content">
        <div className="home-pipeline-icon active">
          <Layers size={18} aria-hidden="true" />
        </div>
        <div className="home-pipeline-text">
          <span className="home-pipeline-title">Application Pipeline</span>
          <span className="home-pipeline-desc">
            <strong>{summary.total}</strong> {summary.total === 1 ? "application" : "applications"}
            {summary.active > 0 && ` · ${summary.active} active`}
            {summary.interviews > 0 && ` · ${summary.interviews} interviewing`}
            {summary.offers > 0 && ` · ${summary.offers} offer received`}
          </span>
        </div>
      </div>

      <Link to="/pipeline" className="btn btn-ghost btn-sm home-pipeline-action">
        <span>Open Pipeline</span>
        <ArrowRight size={14} aria-hidden="true" />
      </Link>
    </aside>
  );
}
