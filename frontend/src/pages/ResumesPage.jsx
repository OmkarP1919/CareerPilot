import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import TailoredResult from "../components/TailoredResult";
import { SkeletonCard } from "../components/Skeleton";
import {
  FileText,
  Upload,
  Trash2,
  Star,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  Calendar,
  HardDrive,
  Sparkles,
  GraduationCap,
  Briefcase,
  Folder,
  Award,
  Mail,
  MapPin,
  Link,
  XCircle,
  RefreshCw,
  Phone,
  Wand2,
  FileDown,
} from "lucide-react";

const PARSING_STATUS_LABEL = {
  pending: "Pending analysis",
  processing: "Processing...",
  completed: "Analyzed",
  failed: "Analysis failed",
};

export default function ResumesPage() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Resume Insights modal state.
  const [insightsResume, setInsightsResume] = useState(null);
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState(null);

  // Tailored versions state.
  const [tailored, setTailored] = useState([]);
  const [tailoredLoading, setTailoredLoading] = useState(true);
  const [viewTailored, setViewTailored] = useState(null);
  const [downloadingKey, setDownloadingKey] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchResumes = useCallback(async () => {
    try {
      const data = await api.get("/resumes");
      setResumes(Array.isArray(data) ? data : []);
    } catch {
      notify("Failed to load resumes", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTailored = useCallback(async () => {
    setTailoredLoading(true);
    try {
      const data = await api.getTailoredResumes();
      setTailored(Array.isArray(data) ? data : []);
    } catch {
      setTailored([]);
    } finally {
      setTailoredLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResumes();
    fetchTailored();
  }, [fetchResumes, fetchTailored]);

  const handleDownload = async (t, fmt) => {
    const key = `${t.id}:${fmt}`;
    setDownloadingKey(key);
    try {
      await api.downloadTailoredResume(t.id, fmt);
      notify(`${fmt.toUpperCase()} downloaded successfully.`);
    } catch {
      notify("Download failed. Please try again.", "error");
    } finally {
      setDownloadingKey(null);
    }
  };

  const handleUpload = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      notify("Only PDF resume files are accepted.", "error");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      notify("File size exceeds 10MB limit.", "error");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const newResume = await api.uploadFile("/resumes", formData);
      setResumes((prev) => [newResume, ...prev]);
      notify("Resume uploaded and analyzed successfully.");
    } catch (err) {
      notify(err.message || "Upload failed. Please try again.", "error");
    } finally {
      setUploading(false);
    }
  };

  const openInsights = async (resume) => {
    setInsightsResume(resume);
    setInsights(null);
    setInsightsError(null);
    setInsightsLoading(true);
    try {
      const data = await api.get(`/resumes/${resume.id}/parsed`);
      setInsights(data);
    } catch (err) {
      setInsightsError(err.message || "Failed to load resume insights.");
    } finally {
      setInsightsLoading(false);
    }
  };

  const reparse = async () => {
    if (!insightsResume) return;
    notify("Re-analyzing resume...", "success");
    setInsightsLoading(true);
    try {
      const data = await api.post(`/resumes/${insightsResume.id}/parse`, {});
      setInsights(data);
      setInsightsError(null);
      notify("Resume re-analyzed successfully.");
      fetchResumes();
    } catch (err) {
      setInsightsError(err.message || "Re-analysis failed.");
      setInsights(null);
    } finally {
      setInsightsLoading(false);
    }
  };

  const closeInsights = () => {
    setInsightsResume(null);
    setInsights(null);
    setInsightsError(null);
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0]);
      e.target.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const handleSetMaster = async (id) => {
    try {
      const updated = await api.put(`/resumes/${id}/master`);
      setResumes((prev) =>
        prev.map((r) => (r.id === id ? updated : { ...r, is_master: false }))
      );
      notify("Designated as Master Resume.");
    } catch {
      notify("Failed to set master resume", "error");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this resume version?")) return;
    try {
      await api.delete(`/resumes/${id}`);
      setResumes((prev) => prev.filter((r) => r.id !== id));
      if (insightsResume && insightsResume.id === id) closeInsights();
      notify("Resume deleted.");
    } catch {
      notify("Failed to delete resume", "error");
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return "";
    const kb = parseInt(bytes, 10) / 1024;
    return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`;
  };

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 220, height: 32 }} />
        </div>
        <div className="grid-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const masterResume = resumes.find((r) => r.is_master);

  return (
    <div className="page">
      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Resumes Hub</h1>
            <p>Manage your master career resume and customized versions</p>
          </div>
          {masterResume && (
            <div className="master-resume-badge">
              <Star size={14} className="text-accent" />
              <span>Master Resume Active</span>
            </div>
          )}
        </div>
      </header>

      {notification && (
        <div className={`alert alert-${notification.type}`} role="alert">
          {notification.type === "error" ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{notification.msg}</span>
        </div>
      )}

      {/* === Insights Modal === */}
      <Modal
        isOpen={!!insightsResume}
        onClose={closeInsights}
        title="Resume Insights"
      >
        <InsightsContent
          insights={insights}
          loading={insightsLoading}
          error={insightsError}
          onReparse={reparse}
        />
      </Modal>

      {/* === Upload Zone === */}
      <section className="card">
        <div
          className={`resume-upload-zone ${dragOver ? "drag-over" : ""} ${uploading ? "uploading" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <div className="upload-zone-icon-wrap">
            <Upload size={28} />
          </div>
          <h3 className="upload-zone-title">
            {uploading ? "Uploading & Analyzing PDF..." : "Upload New Resume Version"}
          </h3>
          <p className="upload-zone-subtitle">
            Drag and drop your PDF resume here, or browse your local files
          </p>

          <label className="btn btn-primary btn-sm" style={{ cursor: uploading ? "not-allowed" : "pointer" }}>
            <FileText size={14} />
            <span>{uploading ? "Uploading..." : "Browse PDF Files"}</span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileInput}
              style={{ display: "none" }}
              disabled={uploading}
            />
          </label>

          <span className="upload-zone-hint">PDF format only • Up to 10MB</span>
        </div>
      </section>

      {/* === Resumes List === */}
      <section className="card">
        <div className="card-header">
          <h2>
            <FileCheck size={18} className="text-accent" />
            <span>Your Resume Library ({resumes.length})</span>
          </h2>
        </div>

        <div className="card-body">
          {resumes.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No resumes uploaded yet"
              text="Upload your master resume above to unlock automated profile indexing and application attachments."
            />
          ) : (
            <div className="resumes-library-grid">
              {resumes.map((resume) => (
                <div
                  key={resume.id}
                  className={`resume-doc-card ${resume.is_master ? "is-master" : ""}`}
                >
                  <div className="resume-doc-icon">
                    <FileText size={28} />
                  </div>

                  <div className="resume-doc-details">
                    <div className="resume-doc-title-row">
                      <h3 className="resume-doc-name">{resume.original_filename}</h3>
                      {resume.is_master && (
                        <span className="master-badge">
                          <Star size={12} />
                          <span>Master Resume</span>
                        </span>
                      )}
                    </div>

                    <div className="resume-doc-meta">
                      {resume.file_size && (
                        <span className="doc-meta-item">
                          <HardDrive size={13} />
                          <span>{formatSize(resume.file_size)}</span>
                        </span>
                      )}
                      {resume.created_at && (
                        <span className="doc-meta-item">
                          <Calendar size={13} />
                          <span>Uploaded {new Date(resume.created_at).toLocaleDateString()}</span>
                        </span>
                      )}
                      <span className={`parsing-status-chip parsing-${resume.parsing_status || "pending"}`}>
                        {resume.parsing_status === "completed" ? (
                          <CheckCircle2 size={12} />
                        ) : resume.parsing_status === "failed" ? (
                          <AlertCircle size={12} />
                        ) : (
                          <RefreshCw size={12} />
                        )}
                        <span>{PARSING_STATUS_LABEL[resume.parsing_status || "pending"]}</span>
                      </span>
                    </div>
                  </div>

                  <div className="resume-doc-actions">
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => openInsights(resume)}
                      type="button"
                    >
                      <Sparkles size={14} />
                      <span>Insights</span>
                    </button>
                    {!resume.is_master && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleSetMaster(resume.id)}
                        type="button"
                      >
                        <Star size={14} />
                        <span>Set as Master</span>
                      </button>
                    )}
                    <button
                      className="btn btn-ghost btn-icon btn-sm btn-danger"
                      onClick={() => handleDelete(resume.id)}
                      title="Delete Resume"
                      type="button"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Tailored Resume Versions === */}
      <section className="card">
        <div className="card-header">
          <h2>
            <Wand2 size={18} className="text-accent" />
            <span>Tailored Resume Versions ({tailored.length})</span>
          </h2>
        </div>

        <div className="card-body">
          {tailoredLoading ? (
            <div className="resume-insights-loading">
              <div className="spinner" />
              <p>Loading tailored versions...</p>
            </div>
          ) : tailored.length === 0 ? (
            <EmptyState
              icon={Wand2}
              title="No tailored versions yet"
              text="Open a job and use Tailor My Resume to create a version tuned for that role. Your original resume is never modified."
            />
          ) : (
            <div className="tailored-versions-list">
              {tailored.map((t) => (
                <div className="tailored-version-row" key={t.id}>
                  <div className="tailored-version-icon">
                    <Wand2 size={18} />
                  </div>
                  <div className="tailored-version-details">
                    <strong className="tailored-version-title">
                      {t.job_title || "Untitled job"}
                      {t.job_company ? ` at ${t.job_company}` : ""}
                    </strong>
                    <span className="tailored-version-sub">
                      {t.source_resume_name || "Resume"}
                      {t.created_at
                        ? ` · Created ${new Date(t.created_at).toLocaleDateString()}`
                        : ""}
                    </span>
                  </div>
                  <div className="tailored-version-actions">
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleDownload(t, "pdf")}
                      type="button"
                      disabled={!!downloadingKey}
                    >
                      {downloadingKey === `${t.id}:pdf` ? <RefreshCw size={14} className="spin" /> : <FileDown size={14} />}
                      <span>PDF</span>
                    </button>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleDownload(t, "docx")}
                      type="button"
                      disabled={!!downloadingKey}
                    >
                      {downloadingKey === `${t.id}:docx` ? <RefreshCw size={14} className="spin" /> : <FileDown size={14} />}
                      <span>DOCX</span>
                    </button>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => setViewTailored(t)}
                      type="button"
                    >
                      <Sparkles size={14} />
                      <span>View</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Tailored Version Viewer Modal === */}
      <Modal
        isOpen={!!viewTailored}
        onClose={() => setViewTailored(null)}
        title="Tailored Resume Version"
        wide
      >
        {viewTailored && (
          <div className="tailored-version-modal-body">
            <TailoredResult
              result={viewTailored}
              jobTitle={viewTailored.job_title}
              jobCompany={viewTailored.job_company}
              hideActions
            />
          </div>
        )}
      </Modal>
    </div>
  );
}

function InsightsContent({ insights, loading, error, onReparse }) {
  if (loading) {
    return (
      <div className="resume-insights-loading">
        <div className="spinner" />
        <p>Analyzing resume...</p>
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="resume-insight-error">
        <XCircle size={20} />
        <div>
          <strong>Could not load resume insights.</strong>
          <p>{error || "An unexpected error occurred."}</p>
        </div>
      </div>
    );
  }

  const status = insights.parsing_status || "pending";
  const data = insights.data || {};
  const basic = data.basic_info || {};
  const skills = data.skills || [];
  const education = data.education || [];
  const experience = data.experience || [];
  const projects = data.projects || [];
  const certifications = data.certifications || [];

  let summaryBlock = null;
  let detailsBlock = null;

  if (status === "failed" || insights.parsing_error) {
    summaryBlock = (
      <div className="resume-insight-error">
        <AlertCircle size={20} />
        <div>
          <strong>We couldn't analyze this resume fully.</strong>
          <p>{insights.parsing_error || "Resume analysis failed."}</p>
        </div>
      </div>
    );
  } else if (status === "pending" || status === "processing") {
    summaryBlock = (
      <div className="resume-insight-empty">
        <RefreshCw size={20} />
        <p>This resume has not been analyzed yet.</p>
        <button className="btn btn-primary btn-sm" onClick={onReparse} type="button">
          <RefreshCw size={14} />
          <span>Analyze Resume</span>
        </button>
      </div>
    );
  } else if (!skills.length && !education.length && !experience.length && !projects.length && !certifications.length) {
    summaryBlock = (
      <div className="resume-insight-empty">
        <Sparkles size={20} />
        <p>No structured information could be extracted from this resume.</p>
      </div>
    );
  } else {
    summaryBlock = (
      <div className="resume-insight-summary">
        <span className="resume-insight-success-line">
          <CheckCircle2 size={14} />
          Resume analyzed successfully
        </span>
        <div className="resume-insight-counts">
          <InsightCount icon={GraduationCap} label="Skills" value={skills.length} />
          <InsightCount icon={FileText} label="Education" value={education.length} />
          <InsightCount icon={Briefcase} label="Experience" value={experience.length} />
          <InsightCount icon={Folder} label="Projects" value={projects.length} />
          <InsightCount icon={Award} label="Certifications" value={certifications.length} />
        </div>
      </div>
    );

    detailsBlock = (
      <div className="resume-insight-details">
        {basic && Object.keys(basic).length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Contact & Basic Info</h4>
            <div className="insight-basic-grid">
              {basic.name && (
                <span className="insight-basic-item"><strong>{basic.name}</strong></span>
              )}
              {basic.email && (
                <span className="insight-basic-item"><Mail size={13} /><span>{basic.email}</span></span>
              )}
              {basic.phone && (
                <span className="insight-basic-item"><Phone size={13} /><span>{basic.phone}</span></span>
              )}
              {basic.location && (
                <span className="insight-basic-item"><MapPin size={13} /><span>{basic.location}</span></span>
              )}
              {basic.linkedin && (
                <span className="insight-basic-item"><Link size={13} /><span>{basic.linkedin}</span></span>
              )}
              {basic.github && (
                <span className="insight-basic-item"><Link size={13} /><span>{basic.github}</span></span>
              )}
              {basic.portfolio && (
                <span className="insight-basic-item"><Link size={13} /><span>{basic.portfolio}</span></span>
              )}
            </div>
          </div>
        )}

        {skills.length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Skills ({skills.length})</h4>
            <div className="insight-tags">
              {skills.map((s, i) => (
                <span className="skill-tag" key={`${s}-${i}`}>{s}</span>
              ))}
            </div>
          </div>
        )}

        {education.length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Education ({education.length})</h4>
            {education.map((e, i) => (
              <div className="insight-entry" key={`edu-${i}`}>
                <strong>{[e.degree, e.field_of_study].filter(Boolean).join(" · ") || "Education"}</strong>
                {e.institution && <span className="insight-muted">{e.institution}</span>}
                {e.graduation_year && <span className="insight-muted">· {e.graduation_year}</span>}
              </div>
            ))}
          </div>
        )}

        {experience.length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Experience ({experience.length})</h4>
            {experience.map((x, i) => (
              <div className="insight-entry" key={`exp-${i}`}>
                <strong>{[x.job_title, x.company].filter(Boolean).join(" — ") || "Experience"}</strong>
                {x.dates && <span className="insight-muted">{x.dates}</span>}
                {x.description && <p className="insight-desc">{x.description}</p>}
              </div>
            ))}
          </div>
        )}

        {projects.length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Projects ({projects.length})</h4>
            {projects.map((p, i) => (
              <div className="insight-entry" key={`proj-${i}`}>
                <strong>{p.name || "Project"}</strong>
                {p.technologies && p.technologies.length > 0 && (
                  <div className="insight-tags">
                    {p.technologies.map((t, j) => (
                      <span className="skill-tag" key={`${t}-${j}`}>{t}</span>
                    ))}
                  </div>
                )}
                {p.description && <p className="insight-desc">{p.description}</p>}
              </div>
            ))}
          </div>
        )}

        {certifications.length > 0 && (
          <div className="insight-section">
            <h4 className="insight-section-title">Certifications ({certifications.length})</h4>
            <div className="insight-tags">
              {certifications.map((c, i) => (
                <span className="skill-tag" key={`cert-${i}`}>{c}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="resume-insights">
      <div className="resume-insights-header">
        <span className={`parsing-status-chip parsing-${status}`}>
          {status === "completed" ? <CheckCircle2 size={12} /> : status === "failed" ? <XCircle size={12} /> : <RefreshCw size={12} />}
          <span>{PARSING_STATUS_LABEL[status] || status}</span>
        </span>
        {status === "completed" && insights.parsing_error && (
          <button className="btn btn-ghost btn-sm" onClick={onReparse} type="button">
            <RefreshCw size={14} />
            <span>Re-analyze</span>
          </button>
        )}
        {(status === "failed" || status === "pending" || status === "processing") && (
          <button className="btn btn-ghost btn-sm" onClick={onReparse} type="button">
            <RefreshCw size={14} />
            <span>Re-analyze</span>
          </button>
        )}
      </div>

      {summaryBlock}
      {detailsBlock}
    </div>
  );
}

function InsightCount({ icon: Icon, label, value }) {
  return (
    <div className="insight-count">
      <span className="insight-count-icon"><Icon size={14} /></span>
      <span className="insight-count-value">{value}</span>
      <span className="insight-count-label">{label}</span>
    </div>
  );
}
