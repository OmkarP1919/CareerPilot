import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import { SkeletonCard } from "../components/Skeleton";
import {
  ArrowLeft,
  MapPin,
  Briefcase,
  BarChart3,
  ExternalLink,
  Layers,
  Sparkles,
  Building2,
  Globe,
  Clock,
} from "lucide-react";

export default function JobDetailsPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadJob = async () => {
      try {
        const data = await api.get(`/jobs/${id}`);
        setJob(data);
      } catch {
        setError("Opportunity details could not be found.");
      } finally {
        setLoading(false);
      }
    };
    loadJob();
  }, [id]);

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 300, height: 32 }} />
        </div>
        <div className="grid-2">
          <SkeletonCard lines={6} />
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="page">
        <div className="page-header">
          <Link to="/discover" className="btn btn-ghost btn-sm">
            <ArrowLeft size={16} />
            <span>Back to Opportunities</span>
          </Link>
          <h1 style={{ marginTop: "var(--space-4)" }}>Opportunity Not Found</h1>
          <p>{error || "This role may have been removed or is no longer available."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* === Navigation Breadcrumb === */}
      <div className="page-nav-breadcrumb">
        <Link to="/discover" className="btn btn-ghost btn-sm">
          <ArrowLeft size={16} />
          <span>Back to Opportunities</span>
        </Link>
      </div>

      {/* === Hero Role Header === */}
      <header className="job-workspace-header">
        <div className="job-workspace-top">
          <div className="job-workspace-brand">
            <div className="job-workspace-logo">
              <Building2 size={24} />
            </div>
            <div>
              <span className="job-workspace-company">{job.company}</span>
              <h1 className="job-workspace-title">{job.title}</h1>
            </div>
          </div>

          <div className="job-workspace-primary-cta">
            <Link to={`/discover/${job.id}/match`} className="btn btn-primary btn-lg">
              <Sparkles size={18} />
              <span>Run Match Analysis</span>
            </Link>
          </div>
        </div>

        <div className="job-workspace-meta-chips">
          {job.location && (
            <div className="meta-chip">
              <MapPin size={14} />
              <span>{job.location}</span>
            </div>
          )}
          {job.employment_type && (
            <div className="meta-chip">
              <Briefcase size={14} />
              <span>{job.employment_type}</span>
            </div>
          )}
          {job.experience_level && (
            <div className="meta-chip">
              <BarChart3 size={14} />
              <span>{job.experience_level}</span>
            </div>
          )}
          {job.source && (
            <div className="meta-chip">
              <Globe size={14} />
              <span>Source: {job.source}</span>
            </div>
          )}
          {job.created_at && (
            <div className="meta-chip">
              <Clock size={14} />
              <span>Discovered {new Date(job.created_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>
      </header>

      {/* === Decision Workspace Two-Column Grid === */}
      <div className="job-workspace-grid">
        {/* Left Column: Description & Responsibilities */}
        <div className="job-workspace-main">
          <section className="card">
            <div className="card-header">
              <h2>Role Description & Context</h2>
            </div>
            <div className="card-body">
              {job.description ? (
                <div className="job-description-content">
                  {job.description.split("\n").map((para, i) =>
                    para.trim() ? <p key={i}>{para}</p> : null
                  )}
                </div>
              ) : (
                <p className="text-secondary">
                  No detailed description provided for this listing. You can run Match Analysis using the required skills.
                </p>
              )}
            </div>
          </section>
        </div>

        {/* Right Column: Required Skills & Action Deck */}
        <aside className="job-workspace-sidebar">
          {/* Match Analysis Callout */}
          <div className="card card-highlight">
            <div className="card-header">
              <h3>
                <Sparkles size={16} className="text-accent" />
                <span>AI Fit Evaluation</span>
              </h3>
            </div>
            <div className="card-body">
              <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>
                Compare your technical skills, projects, and work experience against this position's requirements.
              </p>
              <Link to={`/discover/${job.id}/match`} className="btn btn-primary btn-block">
                <Sparkles size={16} />
                <span>Inspect Match Breakdown</span>
              </Link>
            </div>
          </div>

          {/* Required Skills */}
          {job.required_skills?.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3>Required Skills ({job.required_skills.length})</h3>
              </div>
              <div className="card-body">
                <div className="job-skills-tags-wrap">
                  {job.required_skills.map((s) => (
                    <span key={s} className="skill-tag">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Application Pipeline Action */}
          <div className="card">
            <div className="card-header">
              <h3>Take Action</h3>
            </div>
            <div className="card-body">
              <Link to="/pipeline" className="btn btn-outline btn-block">
                <Layers size={16} />
                <span>Track in Application Pipeline</span>
              </Link>

              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary btn-block"
                  style={{ marginTop: "var(--space-2)" }}
                >
                  <ExternalLink size={16} />
                  <span>Apply on Company Site</span>
                </a>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
