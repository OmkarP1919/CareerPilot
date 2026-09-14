import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import TailoredResult from "../components/TailoredResult";
import CoverLetterModal from "../components/CoverLetterModal";
import { SkeletonCard } from "../components/Skeleton";
import {
  FileText,
  Upload,
  Trash2,
  CheckCircle2,
  AlertCircle,
  FileDown,
  Eye,
} from "lucide-react";

export default function ResumesPage() {
  const { t } = useTranslation();
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Resume Insights state
  const [insightsResume, setInsightsResume] = useState(null);
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState(null);

  // Tailored versions state
  const [tailored, setTailored] = useState([]);
  const [tailoredLoading, setTailoredLoading] = useState(true);
  const [viewTailored, setViewTailored] = useState(null);
  const [downloadingKey, setDownloadingKey] = useState(null);

  // Cover letters state
  const [coverLetters, setCoverLetters] = useState([]);
  const [coverLoading, setCoverLoading] = useState(true);
  const [viewCover, setViewCover] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchResumes = useCallback(async () => {
    try {
      const data = await api.get("/resumes");
      setResumes(Array.isArray(data) ? data : []);
    } catch {
      notify("Failed to load resumes.", "error");
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

  const fetchCoverLetters = useCallback(async () => {
    setCoverLoading(true);
    try {
      const data = await api.getCoverLetters();
      setCoverLetters(Array.isArray(data) ? data : []);
    } catch {
      setCoverLetters([]);
    } finally {
      setCoverLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResumes();
    fetchTailored();
    fetchCoverLetters();
  }, [fetchResumes, fetchTailored, fetchCoverLetters]);

  const handleFileUpload = async (file) => {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
      notify("Please upload a standard PDF resume file.", "error");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      notify("File exceeds the 10MB maximum upload limit.", "error");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await api.uploadFile("/resumes", formData);
      notify("Resume uploaded and parsed successfully!");
      await fetchResumes();
    } catch (err) {
      notify(err.message || "Failed to upload and parse resume.", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteResume = async (id) => {
    if (!window.confirm("Are you sure you want to delete this resume?")) return;
    try {
      await api.delete(`/resumes/${id}`);
      setResumes((prev) => prev.filter((r) => r.id !== id));
      notify("Resume deleted successfully.");
    } catch (err) {
      notify("Failed to delete resume.", "error");
    }
  };

  const handleViewInsights = async (resume) => {
    setInsightsResume(resume);
    setInsights(null);
    setInsightsError(null);
    setInsightsLoading(true);

    try {
      const data = await api.get(`/resumes/${resume.id}/parsed`);
      setInsights(data);
    } catch (err) {
      setInsightsError("Could not retrieve parsed resume insights.");
    } finally {
      setInsightsLoading(false);
    }
  };

  const handleDownloadTailored = async (item, fmt) => {
    const key = `${item.id}:${fmt}`;
    setDownloadingKey(key);
    try {
      await api.downloadTailoredResume(item.id, fmt);
      notify(`${fmt.toUpperCase()} downloaded successfully!`);
    } catch (err) {
      notify("Download failed. Please try again.", "error");
    } finally {
      setDownloadingKey(null);
    }
  };

  const handleDeleteCoverLetter = async (id) => {
    if (!window.confirm(t("cover.deleteConfirm", "Delete this cover letter?"))) return;
    try {
      await api.deleteCoverLetter(id);
      setCoverLetters((prev) => prev.filter((cl) => cl.id !== id));
      if (viewCover?.id === id) setViewCover(null);
      notify(t("cover.deleted", "Cover letter deleted."));
    } catch {
      notify(t("cover.errGeneric", "Something went wrong. Please try again."), "error");
    }
  };

  // If viewing tailored resume preview
  if (viewTailored) {
    return (
      <TailoredResult
        result={viewTailored}
        job={viewTailored.job || { title: viewTailored.job_title || "Target Role", company: viewTailored.company_name || "Company" }}
        onBack={() => setViewTailored(null)}
      />
    );
  }

  // /resumes/{id}/parsed returns data nested under `data`; normalise once here
  // so the insights modal reads the actual backend contract.
  const insightsParsed =
    insights && !Array.isArray(insights) && insights.data && typeof insights.data === "object"
      ? insights.data
      : insights || {};

  return (
    <div className="page resumes-page">
      {/* Toast Notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{t("resume.title", "My Resume")}</h1>
            <p>{t("resume.subtitle", "Keep your resumes ready for every opportunity.")}</p>
          </div>

          <div className="page-header-actions">
            <label className="btn btn-primary cursor-pointer">
              <Upload size={16} />
              <span>{uploading ? "Uploading..." : t("action.uploadResume", "Upload Resume")}</span>
              <input
                type="file"
                accept=".pdf,application/pdf"
                className="sr-only"
                disabled={uploading}
                onChange={(e) => handleFileUpload(e.target.files?.[0])}
              />
            </label>
          </div>
        </div>
      </header>

      {/* Drag and Drop Zone */}
      <div
        className={`resume-dropzone ${dragOver ? "drag-over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFileUpload(e.dataTransfer.files?.[0]);
        }}
      >
        <div className="dropzone-icon">
          <Upload size={24} />
        </div>
        <div className="dropzone-text">
          <span className="dropzone-title">Upload your original PDF resume</span>
          <span className="dropzone-sub">Drag and drop here, or click above to browse (Max 10MB)</span>
        </div>
      </div>

      {/* =========================================================================
          SECTION 1: YOUR MASTER RESUMES
          ========================================================================= */}
      <section className="resumes-section">
        <div className="section-label-row">
          <span className="section-eyebrow">{t("resume.yourResumes", "YOUR RESUMES")}</span>
        </div>

        {loading ? (
          <SkeletonCard />
        ) : resumes.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No original resume uploaded yet"
            description="Upload your standard PDF resume to enable AI tailoring and automatic skill extraction."
          />
        ) : (
          <div className="resumes-grid">
            {resumes.map((r) => {
              const isParsed = r.parsing_status === "completed";
              const parsed = r.parsed_data || {};
              const skillsCount = Array.isArray(parsed.skills) ? parsed.skills.length : 0;
              const expCount = Array.isArray(parsed.experience) ? parsed.experience.length : 0;
              const projCount = Array.isArray(parsed.projects) ? parsed.projects.length : 0;
              const eduCount = Array.isArray(parsed.education) ? parsed.education.length : 0;
              const totalExtracted = skillsCount + expCount + projCount + eduCount;

              let statusTone = "neutral";
              let statusLabel = r.parsing_status || "Processing";
              if (isParsed) {
                const parseErr = r.parsing_error || "";
                if (/scanned|image/i.test(parseErr)) {
                  statusTone = "warn";
                  statusLabel = "This resume appears to be image-based or scanned.";
                } else if (parseErr) {
                  statusTone = "warn";
                  statusLabel = "Limited information extracted";
                } else if (totalExtracted === 0) {
                  statusTone = "warn";
                  statusLabel = "Limited information extracted";
                } else {
                  statusTone = "success";
                  statusLabel = t("resume.parsedSuccess", "Parsed successfully");
                }
              } else if (r.parsing_status === "failed") {
                statusTone = "warn";
                statusLabel = "Parsing failed";
              }

              return (
                <div key={r.id} className="card resume-card-original">
                  <div className="resume-card-top">
                    <div className="resume-icon-badge">
                      <FileText size={20} className="text-accent" />
                    </div>

                    <div className="resume-main-details">
                      <h3 className="resume-filename">{r.filename}</h3>
                      <div className="resume-status-line">
                        <span className="badge-original">Original Resume</span>
                        {isParsed ? (
                          <span className={`parse-status ${statusTone}`}>
                            {statusTone === "success" ? (
                              <CheckCircle2 size={13} />
                            ) : (
                              <AlertCircle size={13} />
                            )}
                            <span>{statusLabel}</span>
                          </span>
                        ) : r.parsing_status === "failed" ? (
                          <span className="parse-status warn">
                            <AlertCircle size={13} />
                            <span>{statusLabel}</span>
                          </span>
                        ) : (
                          <span className="parse-status neutral">{statusLabel}</span>
                        )}
                      </div>

                      {/* Quick metrics */}
                      {isParsed && (
                        <div className="resume-metrics-line text-xs text-muted">
                          <span>{skillsCount} skills</span>
                          <span className="dot">•</span>
                          <span>{projCount} projects</span>
                          <span className="dot">•</span>
                          <span>{expCount} experiences</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="resume-card-footer">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleViewInsights(r)}
                      disabled={!isParsed}
                    >
                      <Eye size={14} />
                      <span>{t("resume.viewInsights", "View Insights")}</span>
                    </button>

                    <button
                      type="button"
                      className="btn btn-ghost btn-icon btn-sm text-danger"
                      onClick={() => handleDeleteResume(r.id)}
                      title="Delete Resume"
                      aria-label="Delete Resume"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* =========================================================================
          SECTION 2: TAILORED VERSIONS
          ========================================================================= */}
      <section className="tailored-section" style={{ marginTop: "var(--space-8)" }}>
        <div className="section-label-row">
          <span className="section-eyebrow">{t("resume.tailoredVersions", "TAILORED VERSIONS")}</span>
        </div>

        {tailoredLoading ? (
          <SkeletonCard />
        ) : tailored.length === 0 ? (
          <div className="card empty-tailored-card">
            <p className="text-secondary text-sm">
              No tailored versions created yet. When you tailor a resume for a specific job, it will be saved here for quick PDF and DOCX export.
            </p>
          </div>
        ) : (
          <div className="tailored-resumes-list">
            {tailored.map((tItem) => (
              <div key={tItem.id} className="card tailored-resume-row">
                <div className="tailored-info">
                  <div className="tailored-title-row">
                    <strong>{tItem.job_title || tItem.target_role || "Tailored Position"}</strong>
                    {tItem.company_name && <span className="tailored-company">· {tItem.company_name}</span>}
                  </div>
                  <span className="tailored-date text-xs text-muted">
                    Created {tItem.created_at ? new Date(tItem.created_at).toLocaleDateString() : "Recently"}
                  </span>
                </div>

                <div className="tailored-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setViewTailored(tItem)}
                  >
                    <Eye size={14} />
                    <span>View</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDownloadTailored(tItem, "pdf")}
                    disabled={downloadingKey === `${tItem.id}:pdf`}
                  >
                    <FileDown size={14} />
                    <span>{downloadingKey === `${tItem.id}:pdf` ? "..." : "PDF"}</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDownloadTailored(tItem, "docx")}
                    disabled={downloadingKey === `${tItem.id}:docx`}
                  >
                    <FileDown size={14} />
                    <span>{downloadingKey === `${tItem.id}:docx` ? "..." : "DOCX"}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* =========================================================================
          SECTION 3: COVER LETTERS
          ========================================================================= */}
      <section className="tailored-section" style={{ marginTop: "var(--space-8)" }}>
        <div className="section-label-row">
          <span className="section-eyebrow">{t("cover.shortTitle", "COVER LETTERS")}</span>
        </div>

        {coverLoading ? (
          <SkeletonCard />
        ) : coverLetters.length === 0 ? (
          <div className="card empty-tailored-card">
            <p className="text-secondary text-sm">
              {t("cover.emptyDesc", "Create one from any job you're interested in.")}
            </p>
          </div>
        ) : (
          <div className="tailored-resumes-list">
            {coverLetters.map((cl) => (
              <div key={cl.id} className="card tailored-resume-row">
                <div className="tailored-info">
                  <div className="tailored-title-row">
                    <strong>{cl.job_title || "Cover Letter"}</strong>
                    {cl.job_company && <span className="tailored-company">· {cl.job_company}</span>}
                  </div>
                  <span className="tailored-date text-xs text-muted">
                    {t("cover.createdOn", "Created")} {cl.created_at ? new Date(cl.created_at).toLocaleDateString() : "Recently"}
                  </span>
                </div>

                <div className="tailored-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setViewCover(cl)}
                  >
                    <Eye size={14} />
                    <span>{t("cover.view", "View")}</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-ghost btn-icon btn-sm text-danger"
                    onClick={() => handleDeleteCoverLetter(cl.id)}
                    title={t("cover.delete", "Delete")}
                    aria-label={t("cover.delete", "Delete")}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Cover letter view modal */}
      {viewCover && (
        <CoverLetterModal
          isOpen={Boolean(viewCover)}
          onClose={() => setViewCover(null)}
          job={{ title: viewCover.job_title, company: viewCover.job_company }}
          viewOnly
          initialLetter={viewCover}
        />
      )}

      {/* =========================================================================
          RESUME INSIGHTS MODAL (Clean, Structured Summary)
          ========================================================================= */}
      {insightsResume && (
        <Modal
          isOpen={Boolean(insightsResume)}
          onClose={() => setInsightsResume(null)}
          title={`Resume Insights: ${insightsResume.filename}`}
        >
          {insightsLoading ? (
            <div className="insights-loading">
              <div className="spinner-inline" />
              <p>Loading parsed resume structure...</p>
            </div>
          ) : insightsError ? (
            <div className="alert alert-error">
              <AlertCircle size={16} />
              <span>{insightsError}</span>
            </div>
          ) : insights ? (
            <div className="resume-insights-content">
              {/* Summary count tiles */}
              <div className="insights-tiles-grid">
                <div className="insight-tile">
                  <span className="tile-number font-mono">{insightsParsed.skills?.length || 0}</span>
                  <span className="tile-label">{t("resume.skillsCount", "Skills")}</span>
                </div>
                <div className="insight-tile">
                  <span className="tile-number font-mono">{insightsParsed.projects?.length || 0}</span>
                  <span className="tile-label">{t("resume.projectsCount", "Projects")}</span>
                </div>
                <div className="insight-tile">
                  <span className="tile-number font-mono">{insightsParsed.experience?.length || 0}</span>
                  <span className="tile-label">{t("resume.expCount", "Experience")}</span>
                </div>
                <div className="insight-tile">
                  <span className="tile-number font-mono">{insightsParsed.education?.length || 0}</span>
                  <span className="tile-label">{t("resume.eduCount", "Education")}</span>
                </div>
              </div>

              {/* Skills section */}
              {insightsParsed.skills?.length > 0 && (
                <div className="insights-section">
                  <h4>Detected Technical Skills</h4>
                  <div className="skills-chips-wrap" style={{ marginTop: "var(--space-2)" }}>
                    {insightsParsed.skills.map((s, i) => (
                      <span key={i} className="skill-chip match">
                        {typeof s === "string" ? s : s.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Experience section */}
              {insightsParsed.experience?.length > 0 && (
                <div className="insights-section">
                  <h4>Work Experience</h4>
                  <div className="insights-exp-list">
                    {insightsParsed.experience.map((exp, i) => (
                      <div key={i} className="insight-exp-item">
                        <div className="exp-title-row">
                          <strong>{exp.title || exp.role || exp.job_title || "Role"}</strong>
                          {exp.company && <span className="text-secondary">· {exp.company}</span>}
                        </div>
                        {(exp.duration || exp.dates) && <span className="text-xs text-muted">{exp.duration || exp.dates}</span>}
                        {exp.description && <p className="text-sm text-secondary">{exp.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Education section */}
              {insightsParsed.education?.length > 0 && (
                <div className="insights-section">
                  <h4>Education</h4>
                  <div className="insights-exp-list">
                    {insightsParsed.education.map((edu, i) => (
                      <div key={i} className="insight-exp-item">
                        <div className="exp-title-row">
                          <strong>{edu.degree || "Qualification"}</strong>
                          {edu.institution && <span className="text-secondary">· {edu.institution}</span>}
                        </div>
                        {(edu.graduation_year || edu.field_of_study) && (
                          <span className="text-xs text-muted">
                            {[edu.graduation_year, edu.field_of_study].filter(Boolean).join(" · ")}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Projects section */}
              {insightsParsed.projects?.length > 0 && (
                <div className="insights-section">
                  <h4>Projects</h4>
                  <div className="insights-proj-list">
                    {insightsParsed.projects.map((p, i) => (
                      <div key={i} className="insight-proj-item">
                        <strong>{p.name || p.title || "Project"}</strong>
                        {p.technologies && <span className="text-xs text-muted">{Array.isArray(p.technologies) ? p.technologies.join(", ") : p.technologies}</span>}
                        {p.description && <p className="text-sm text-secondary">{p.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setInsightsResume(null)}
                >
                  Close
                </button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  );
}
