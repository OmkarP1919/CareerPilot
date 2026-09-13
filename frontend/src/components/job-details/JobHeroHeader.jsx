import { Link } from "react-router-dom";
import ScoreBadge from "../ScoreBadge";
import { ArrowLeft, MapPin, Briefcase, Clock, DollarSign } from "lucide-react";

export default function JobHeroHeader({ job, score }) {
  const matchTier =
    score >= 80
      ? "High Match"
      : score >= 60
      ? "Strong Match"
      : score >= 40
      ? "Moderate Match"
      : score > 0
      ? "Low Match"
      : "Match Pending";

  const postedDate = job.created_at
    ? new Date(job.created_at).toLocaleDateString()
    : "Recently active";

  return (
    <div className="job-details-hero card">
      <div className="details-breadcrumb">
        <Link to="/discover" className="breadcrumb-link" aria-label="Back to Opportunities">
          <ArrowLeft size={16} aria-hidden="true" />
          <span>Back to Opportunities</span>
        </Link>
      </div>

      <div className="hero-main-row">
        <div className="hero-info-col">
          <div className="hero-company-line">
            <span className="hero-company-name">{job.company}</span>
            {job.location && (
              <>
                <span className="meta-sep" aria-hidden="true">•</span>
                <span className="hero-location">
                  <MapPin size={14} aria-hidden="true" />
                  <span>{job.location}</span>
                </span>
              </>
            )}
          </div>

          <h1 className="job-hero-title">{job.title}</h1>

          <div className="job-hero-meta">
            {job.work_mode && job.work_mode !== "unspecified" && (
              <span className="job-meta-pill work-mode">{job.work_mode}</span>
            )}
            {job.employment_type && (
              <span className="job-meta-pill">
                <Briefcase size={13} aria-hidden="true" />
                <span>{job.employment_type}</span>
              </span>
            )}
            {job.experience_level && (
              <span className="job-meta-pill">{job.experience_level}</span>
            )}
            {(job.salary_min != null || job.salary_max != null || job.salary) && (
              <span className="job-meta-pill salary">
                <DollarSign size={13} aria-hidden="true" />
                <span>
                  {typeof job.salary === "string"
                    ? job.salary
                    : `${job.salary_min != null ? job.salary_min.toLocaleString() : ""}${
                        job.salary_min && job.salary_max ? " - " : ""
                      }${job.salary_max != null ? job.salary_max.toLocaleString() : ""}${
                        job.salary_currency ? ` ${job.salary_currency}` : ""
                      }`}
                </span>
              </span>
            )}
            <span className="job-meta-pill date">
              <Clock size={13} aria-hidden="true" />
              <span>{postedDate}</span>
            </span>
          </div>
        </div>

        <div className="hero-score-col" aria-label={`Match Score: ${score}% (${matchTier})`}>
          <div className="hero-score-box">
            <ScoreBadge score={score} size="large" />
            <span className="hero-score-tier">{matchTier}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
