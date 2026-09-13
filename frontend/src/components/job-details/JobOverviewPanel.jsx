import { Code2, FileText } from "lucide-react";
import { useTranslation } from "../../context/LanguageContext";

export default function JobOverviewPanel({ job }) {
  const { t } = useTranslation();
  const skills = Array.isArray(job.required_skills) ? job.required_skills : [];

  return (
    <div className="job-overview-stack">
      {/* Required Skills Section */}
      {skills.length > 0 && (
        <section className="card job-overview-card" aria-labelledby="required-skills-heading">
          <div className="card-header">
            <h2 id="required-skills-heading" className="panel-section-title">
              <Code2 size={18} className="text-accent" aria-hidden="true" />
              <span>{t("jobDetail.skills", "Required Skills")} ({skills.length})</span>
            </h2>
          </div>
          <div className="card-body">
            <div className="skills-chips-wrap">
              {skills.map((skill) => (
                <span key={skill} className="skill-chip match">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Role Overview & Details */}
      <section className="card job-overview-card" aria-labelledby="job-description-heading">
        <div className="card-header">
          <h2 id="job-description-heading" className="panel-section-title">
            <FileText size={18} className="text-accent" aria-hidden="true" />
            <span>Role Overview & Responsibilities</span>
          </h2>
        </div>
        <div className="card-body job-description-body">
          {job.description ? (
            <div className="formatted-description">
              {job.description.split("\n").map((para, i) =>
                para.trim() ? (
                  para.trim().startsWith("•") || para.trim().startsWith("-") || para.trim().startsWith("*") ? (
                    <li key={i} className="description-list-item">
                      {para.trim().replace(/^[-•*]\s*/, "")}
                    </li>
                  ) : (
                    <p key={i}>{para}</p>
                  )
                ) : (
                  <br key={i} />
                )
              )}
            </div>
          ) : (
            <div className="empty-description-prompt">
              <p className="text-secondary text-sm">
                No detailed text description was provided for this opportunity.
              </p>
              <p className="text-muted text-xs" style={{ marginTop: "var(--space-1)" }}>
                CareerPilot matches your profile against the role title, location, and declared skills. Use &ldquo;Tailor Resume&rdquo; to target this position.
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
