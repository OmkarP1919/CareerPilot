import {
  Briefcase,
  Folder,
  GraduationCap,
  Award,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Sparkles,
  Wand2,
  RefreshCw,
  ArrowLeft,
  Save,
  Loader2,
  FileDown,
} from "lucide-react";
import { useState } from "react";
import { api } from "../services/api";

function Chips({ items, tone }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="tailored-tags">
      {items.map((s, i) => (
        <span className={`skill-tag ${tone ? `skill-${tone}` : ""}`} key={`${s}-${i}`}>
          {s}
        </span>
      ))}
    </div>
  );
}

function BeforeAfter({ title, before, after }) {
  const hasBefore = Array.isArray(before) ? before.some(Boolean) : Boolean(before);
  return (
    <div className="tailor-ba">
      {title && <h5 className="tailor-ba-title">{title}</h5>}
      <div className="tailor-ba-grid">
        <div className="tailor-ba-col">
          <span className="tailor-ba-label">Original</span>
          <div className="tailor-ba-body">
            {Array.isArray(before) ? (
              hasBefore ? (
                <ul className="tailor-ba-list">
                  {before.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-tertiary">No original content.</p>
              )
            ) : before ? (
              before
            ) : (
              <p className="text-tertiary">No original content.</p>
            )}
          </div>
        </div>
        <div className="tailor-ba-col tailor-ba-col-tailored">
          <span className="tailor-ba-label">Tailored</span>
          <div className="tailor-ba-body">
            {Array.isArray(after) ? (
              after.length ? (
                <ul className="tailor-ba-list">
                  {after.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-tertiary">No tailored content.</p>
              )
            ) : after ? (
              after
            ) : (
              <p className="text-tertiary">No tailored content.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function educText(e) {
  if (!e || typeof e === "string") return e || "";
  return [e.degree, e.field_of_study].filter(Boolean).join(" · ");
}

function educCaption(e) {
  if (!e || typeof e === "string") return "";
  return [e.institution, e.graduation_year].filter(Boolean).join(" · ");
}

export default function TailoredResult({ result, jobTitle, jobCompany, onRegenerate, onTailorAnother, onBack, hideActions = false, regenerating = false }) {
  const original = result.original_content || {};
  const tailored = result.tailored_content || {};

  const [downloading, setDownloading] = useState(null);
  const [downloadMsg, setDownloadMsg] = useState(null);

  const handleDownload = async (fmt) => {
    setDownloading(fmt);
    setDownloadMsg(null);
    try {
      const { filename } = await api.downloadTailoredResume(result.id, fmt);
      setDownloadMsg({
        type: "success",
        text: `${fmt === "pdf" ? "PDF" : "DOCX"} downloaded successfully.${filename ? ` (${filename})` : ""}`,
      });
    } catch {
      setDownloadMsg({ type: "error", text: "Download failed. Please try again." });
    } finally {
      setDownloading(null);
    }
  };

  const changes = result.changes || [];
  const supported = result.supported_keywords_added || [];
  const unsupported = result.unsupported_job_keywords || [];
  const warnings = result.warnings || [];

  const experienceItems = tailored.experience || [];
  const projectItems = tailored.projects || [];
  const skills = tailored.skills || [];
  const emphasized = tailored.emphasized_skills || [];
  const education = tailored.education || [];
  const certifications = tailored.certifications || [];
  const summary = tailored.summary || "";

  return (
    <section className="tailored-result" aria-label="Tailored Resume">
      {/* Result header */}
      <div className="tailored-result-header">
        <div>
          <div className="tailored-result-eyebrow">
            <Sparkles size={15} className="text-accent" />
            <span>SAVED VERSION</span>
          </div>
          <h2 className="tailored-result-title">Tailored Resume</h2>
        </div>
        <div className="tailored-result-meta">
          <div className="tailored-result-meta-item">
            <span className="tailored-result-meta-label">Job</span>
            <span className="tailored-result-meta-value">
              {jobTitle}
              {jobCompany ? ` at ${jobCompany}` : ""}
            </span>
          </div>
          <div className="tailored-result-meta-item">
            <span className="tailored-result-meta-label">Resume</span>
            <span className="tailored-result-meta-value">
              {result.source_resume_name || result.resume_id || "Selected resume"}
            </span>
          </div>
        </div>
      </div>

      {(result.created_at || result.ai_provider) && (
        <p className="tailored-result-submeta">
          <Save size={13} />
          <span>
            Saved{" "}
            {result.created_at
              ? new Date(result.created_at).toLocaleString()
              : "recently"}
            {result.model ? ` · Generated with ${result.model}` : ""}
          </span>
        </p>
      )}

      {/* Trust / safety banner */}
      <div className="tailor-trust-note tailor-trust-banner" role="note">
        <ShieldCheck size={16} />
        <span>
          Your original resume is unchanged. CareerPilot only uses information
          supported by your existing resume/profile — it does not add fabricated
          experience or qualifications.
        </span>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="alert alert-warning" role="alert">
          <AlertTriangle size={16} />
          <div>
            <strong>Please review</strong>
            <ul className="tailor-warning-list">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="card">
        <div className="card-header">
          <h3>Professional Summary</h3>
        </div>
        <div className="card-body">
          {summary ? (
            <p className="tailored-summary-text">{summary}</p>
          ) : (
            <p className="text-tertiary">No summary was generated.</p>
          )}
        </div>
      </div>

      {/* Skills */}
      <div className="card">
        <div className="card-header">
          <h3>
            Skills{" "}
            {emphasized.length > 0 && (
              <span className="tailored-emph-hint">(emphasized: {emphasized.join(", ")})</span>
            )}
          </h3>
        </div>
        <div className="card-body">
          <BeforeAfter before={original.skills || []} after={skills} />
        </div>
      </div>

      {/* Experience */}
      {experienceItems.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>
              <Briefcase size={16} className="text-accent" />
              <span>Experience</span>
            </h3>
          </div>
          <div className="card-body">
            <div className="tailored-entries">
              {experienceItems.map((item, i) => (
                <div className="tailor-entry" key={i}>
                  <div className="tailor-entry-head">
                    <strong>{item.original_title || item.company || "Experience"}</strong>
                    {item.company && item.original_title !== item.company && (
                      <span className="tailor-entry-company">{item.company}</span>
                    )}
                  </div>
                  <BeforeAfter
                    before={item.original_bullets || []}
                    after={item.tailored_bullets || []}
                  />
                  {item.changes && item.changes.length > 0 && (
                    <div className="tailor-entry-changes">
                      <span className="tailor-sub-label">Changes</span>
                      <ul>
                        {item.changes.map((c, j) => (
                          <li key={j}>
                            <CheckCircle2 size={13} className="text-accent" />
                            <span>{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Projects */}
      {projectItems.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>
              <Folder size={16} className="text-accent" />
              <span>Projects</span>
            </h3>
          </div>
          <div className="card-body">
            <div className="tailored-entries">
              {projectItems.map((p, i) => (
                <div className="tailor-entry" key={i}>
                  <div className="tailor-entry-head">
                    <strong>{p.name || "Project"}</strong>
                  </div>
                  <BeforeAfter
                    before={p.original_description}
                    after={p.tailored_description}
                  />
                  {p.changes && p.changes.length > 0 && (
                    <div className="tailor-entry-changes">
                      <span className="tailor-sub-label">Changes</span>
                      <ul>
                        {p.changes.map((c, j) => (
                          <li key={j}>
                            <CheckCircle2 size={13} className="text-accent" />
                            <span>{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Education */}
      {education.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>
              <GraduationCap size={16} className="text-accent" />
              <span>Education</span>
            </h3>
          </div>
          <div className="card-body">
            <ul className="tailor-simple-list">
              {education.map((e, i) => (
                <li key={i}>
                  <strong>{educText(e)}</strong>
                  {educCaption(e) && <span className="text-tertiary"> — {educCaption(e)}</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Certifications */}
      {certifications.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>
              <Award size={16} className="text-accent" />
              <span>Certifications</span>
            </h3>
          </div>
          <div className="card-body">
            <Chips items={certifications} />
          </div>
        </div>
      )}

      {/* Changes made */}
      <div className="card">
        <div className="card-header">
          <h3>Changes Made</h3>
        </div>
        <div className="card-body">
          {changes.length > 0 ? (
            <ul className="match-evidence-list">
              {changes.map((c, i) => (
                <li className="match-evidence-item" key={i}>
                  <CheckCircle2 size={16} className="text-accent" />
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-tertiary">No changes were reported.</p>
          )}
        </div>
      </div>

      {/* Keywords */}
      {(supported.length > 0 || unsupported.length > 0) && (
        <div className="card">
          <div className="card-header">
            <h3>Keywords</h3>
          </div>
          <div className="card-body">
            {supported.length > 0 && (
              <div className="tailored-keyword-block">
                <span className="tailor-sub-label">Relevant Keywords Added</span>
                <Chips items={supported} tone="matched" />
              </div>
            )}
            {unsupported.length > 0 && (
              <div className="tailored-keyword-block">
                <span className="tailor-sub-label">Job Requirements Not Added</span>
                <Chips items={unsupported} tone="missing" />
                <p className="tailor-keyword-note">
                  These requirements were not added because they were not
                  supported by your resume.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Downloads */}
      {result.id && (
        <>
          <div className="tailored-result-downloads" role="group" aria-label="Download resume">
            <span className="tailored-result-downloads-label">Download:</span>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => handleDownload("pdf")}
              type="button"
              disabled={!!downloading}
            >
              {downloading === "pdf" ? <Loader2 size={15} className="spin" /> : <FileDown size={15} />}
              <span>{downloading === "pdf" ? "Downloading PDF..." : "Download PDF"}</span>
            </button>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => handleDownload("docx")}
              type="button"
              disabled={!!downloading}
            >
              {downloading === "docx" ? <Loader2 size={15} className="spin" /> : <FileDown size={15} />}
              <span>{downloading === "docx" ? "Downloading DOCX..." : "Download DOCX"}</span>
            </button>
          </div>
          {downloadMsg && (
            <p
              className={`tailored-download-msg ${downloadMsg.type === "error" ? "tailored-download-msg-error" : ""}`}
              role="status"
            >
              {downloadMsg.text}
            </p>
          )}
        </>
      )}

      {/* Actions */}
      {!hideActions && (
        <div className="tailored-result-actions">
          <button className="btn btn-outline" onClick={onBack} type="button">
            <ArrowLeft size={16} />
            <span>Back to Job</span>
          </button>
          <button className="btn btn-outline" onClick={onTailorAnother} type="button">
            <Wand2 size={16} />
            <span>Tailor Another Resume</span>
          </button>
          <button
            className="btn btn-primary"
            onClick={onRegenerate}
            type="button"
            disabled={regenerating}
          >
            {regenerating ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
            <span>{regenerating ? "Regenerating..." : "Regenerate"}</span>
          </button>
        </div>
      )}
    </section>
  );
}
