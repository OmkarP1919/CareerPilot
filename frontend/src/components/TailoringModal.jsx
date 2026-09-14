import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "./Modal";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import {
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Sparkles,
  Info,
} from "lucide-react";
import {
  isExperienceMatched,
  isProjectMatched,
  deriveInitialSelections,
} from "./tailoringCurationUtils";

function isResumeUsable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

function formatDates(item) {
  if (item.dates) return item.dates;
  if (item.duration) return item.duration;
  const parts = [item.start_date, item.end_date].filter(Boolean);
  return parts.length > 0 ? parts.join(" – ") : null;
}

function formatDesc(item) {
  const text =
    item.description ||
    (Array.isArray(item.responsibilities) ? item.responsibilities.join(". ") : "") ||
    (Array.isArray(item.details) ? item.details.join(". ") : "") ||
    "";
  if (!text) return "";
  return text.length > 140 ? `${text.slice(0, 140)}...` : text;
}

function formatTech(proj) {
  if (Array.isArray(proj.technologies)) return proj.technologies.join(", ");
  if (proj.technologies) return String(proj.technologies);
  if (proj.tech_stack) return String(proj.tech_stack);
  return "";
}



export default function TailoringModal({ job, matchData, isOpen, onClose, onSuccess }) {
  const { t } = useTranslation();
  const [step, setStep] = useState("pick"); // "pick" | "curate" | "loading"
  const [resumes, setResumes] = useState([]);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResume, setSelectedResume] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [parsedLoading, setParsedLoading] = useState(false);
  const [runError, setRunError] = useState(null);

  // Curation state: lists of selected indices
  const [selectedExpIndices, setSelectedExpIndices] = useState([]);
  const [selectedProjIndices, setSelectedProjIndices] = useState([]);

  const loadResumes = useCallback(async () => {
    setResumesLoading(true);
    setResumesError(null);
    setSelectedResume(null);
    setParsedData(null);
    setRunError(null);
    setStep("pick");
    try {
      const data = await api.get("/resumes");
      const list = Array.isArray(data) ? data : [];
      setResumes(list);
      const firstUsable = list.find(isResumeUsable);
      if (firstUsable) setSelectedResume(firstUsable);
    } catch (err) {
      setResumesError(err.message || "Failed to load uploaded resumes.");
    } finally {
      setResumesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadResumes();
    }
  }, [isOpen, loadResumes]);

  const handleClose = () => {
    if (step === "loading") return;
    onClose();
  };

  const proceedToCurate = async () => {
    if (!selectedResume) return;
    setRunError(null);
    setParsedLoading(true);

    try {
      let data = selectedResume.parsed_data;
      if (!data) {
        const res = await api.get(`/resumes/${selectedResume.id}/parsed`);
        data = res?.data || res?.parsed_data || {};
      }
      setParsedData(data || {});

      const experiences = Array.isArray(data?.experience) ? data.experience : [];
      const projects = Array.isArray(data?.projects) ? data.projects : [];

      // Intelligent defaults:
      // If deterministic match evidence identifies one or more source records:
      // select ONLY those identified records.
      // If deterministic match evidence is unavailable OR identifies no usable source records:
      // select ALL records.
      const { selectedExpIndices: initExp, selectedProjIndices: initProj } =
        deriveInitialSelections(data, matchData);
      setSelectedExpIndices(initExp);
      setSelectedProjIndices(initProj);

      setStep("curate");
    } catch (err) {
      setRunError(err.message || "Could not load resume details.");
    } finally {
      setParsedLoading(false);
    }
  };

  const toggleExperience = (index) => {
    setSelectedExpIndices((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const toggleProject = (index) => {
    setSelectedProjIndices((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const runTailor = async () => {
    if (!selectedResume) return;
    setRunError(null);
    setStep("loading");
    try {
      const curation = {
        selected_experience_indices: selectedExpIndices,
        selected_project_indices: selectedProjIndices,
      };
      const result = await api.tailorResume(job.id, selectedResume.id, false, curation);
      onSuccess(result);
    } catch (err) {
      setRunError(err.message || "Resume tailoring could not be completed.");
      setStep("curate");
    }
  };

  const sourceExperiences = Array.isArray(parsedData?.experience)
    ? parsedData.experience
    : [];
  const sourceProjects = Array.isArray(parsedData?.projects)
    ? parsedData.projects
    : [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={t("tailor.title", "AI Resume Tailoring")}
    >
      <div className="tailoring-wizard">
        {/* Step indicator */}
        <div className="wizard-steps-header">
          <span className={`wizard-step ${step === "pick" ? "active" : "done"}`}>
            1. {t("tailor.step1", "Choose Master Resume")}
          </span>
          <span className="wizard-sep">→</span>
          <span
            className={`wizard-step ${
              step === "curate" ? "active" : step === "loading" ? "done" : ""
            }`}
          >
            2. {t("tailor.step2", "Choose What to Include")}
          </span>
          <span className="wizard-sep">→</span>
          <span className={`wizard-step ${step === "loading" ? "active" : ""}`}>
            3. {t("tailor.step3", "Generating")}
          </span>
        </div>

        {/* STEP 1: CHOOSE MASTER RESUME */}
        {step === "pick" && (
          <div className="wizard-step-body">
            <p className="text-secondary text-sm">
              Select the master resume you wish to tailor for{" "}
              <strong>{job?.title}</strong> at <strong>{job?.company}</strong>:
            </p>

            {resumesLoading ? (
              <div className="loading-state">
                <div className="spinner-inline" />
                <p>Loading resumes...</p>
              </div>
            ) : resumesError ? (
              <div className="alert alert-error">
                <AlertCircle size={16} />
                <span>{resumesError}</span>
              </div>
            ) : resumes.length === 0 ? (
              <div className="empty-resumes-prompt">
                <p>No master resumes uploaded yet.</p>
                <Link to="/resumes" className="btn btn-primary btn-sm">
                  Upload Resume First
                </Link>
              </div>
            ) : (
              <div className="resumes-pick-list">
                {resumes.map((r) => {
                  const usable = isResumeUsable(r);
                  return (
                    <label
                      key={r.id}
                      className={`resume-pick-item ${
                        selectedResume?.id === r.id ? "selected" : ""
                      } ${!usable ? "disabled" : ""}`}
                    >
                      <input
                        type="radio"
                        name="tailor_resume_pick"
                        disabled={!usable}
                        checked={selectedResume?.id === r.id}
                        onChange={() => setSelectedResume(r)}
                      />
                      <div className="pick-info">
                        <strong>{r.filename}</strong>
                        <span className="text-xs text-muted">
                          {usable ? "✓ Ready for tailoring" : "Processing required"}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}

            {runError && (
              <div className="alert alert-error" style={{ marginTop: "var(--space-4)" }}>
                <AlertCircle size={16} />
                <span>{runError}</span>
              </div>
            )}

            <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
              <button type="button" className="btn btn-ghost" onClick={handleClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={proceedToCurate}
                disabled={!selectedResume || parsedLoading}
              >
                <span>{parsedLoading ? "Loading..." : "Continue"}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: CHOOSE WHAT TO INCLUDE */}
        {step === "curate" && (
          <div className="wizard-step-body curation-step-body">
            <div className="curation-intro">
              <p className="text-secondary text-sm">
                Choose the experiences and projects from <strong>{selectedResume?.filename}</strong> to
                include for <strong>{job?.title}</strong>. The master resume remains unchanged.
              </p>
            </div>

            {/* Calm informational notice if user explicitly selects zero items */}
            {selectedExpIndices.length === 0 && selectedProjIndices.length === 0 && (
              <div className="alert alert-info curation-empty-notice" role="status">
                <Info size={16} />
                <span>
                  Your tailored resume will focus on the remaining available sections such as summary, skills, and education.
                </span>
              </div>
            )}

            {/* EXPERIENCES SECTION */}
            <div className="curate-section">
              <div className="curate-section-header">
                <h4 className="curate-section-title">
                  Experiences ({selectedExpIndices.length}/{sourceExperiences.length})
                </h4>
                {sourceExperiences.length > 0 && (
                  <div className="curate-section-actions">
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs"
                      onClick={() =>
                        setSelectedExpIndices(sourceExperiences.map((_, i) => i))
                      }
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs"
                      onClick={() => setSelectedExpIndices([])}
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              {sourceExperiences.length === 0 ? (
                <p className="text-xs text-muted">No experiences found in this master resume.</p>
              ) : (
                <div className="curate-cards-list">
                  {sourceExperiences.map((exp, idx) => {
                    const isSelected = selectedExpIndices.includes(idx);
                    const isMatched = isExperienceMatched(exp, matchData);
                    const dates = formatDates(exp);
                    const desc = formatDesc(exp);
                    return (
                      <label
                        key={idx}
                        className={`curate-item-card ${isSelected ? "selected" : ""}`}
                        htmlFor={`exp-checkbox-${idx}`}
                      >
                        <div className="curate-checkbox-wrap">
                          <input
                            id={`exp-checkbox-${idx}`}
                            type="checkbox"
                            className="curate-checkbox"
                            checked={isSelected}
                            onChange={() => toggleExperience(idx)}
                            aria-label={`Include ${exp.role || exp.title || "experience"} at ${
                              exp.company || "company"
                            }`}
                          />
                        </div>
                        <div className="curate-card-content">
                          <div className="curate-card-header">
                            <div className="curate-card-title-group">
                              <strong className="curate-card-title">
                                {exp.role || exp.title || "Experience"}
                              </strong>
                              {exp.company && (
                                <span className="curate-card-subtitle">{exp.company}</span>
                              )}
                            </div>
                            {isMatched && (
                              <span className="curate-badge-match">
                                <CheckCircle2 size={12} />
                                <span>Relevant to job</span>
                              </span>
                            )}
                          </div>
                          {dates && (
                            <span className="curate-card-dates text-xs text-muted">
                              {dates}
                            </span>
                          )}
                          {desc && (
                            <p className="curate-card-desc text-xs text-secondary">{desc}</p>
                          )}
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* PROJECTS SECTION */}
            <div className="curate-section">
              <div className="curate-section-header">
                <h4 className="curate-section-title">
                  Projects ({selectedProjIndices.length}/{sourceProjects.length})
                </h4>
                {sourceProjects.length > 0 && (
                  <div className="curate-section-actions">
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs"
                      onClick={() =>
                        setSelectedProjIndices(sourceProjects.map((_, i) => i))
                      }
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs"
                      onClick={() => setSelectedProjIndices([])}
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              {sourceProjects.length === 0 ? (
                <p className="text-xs text-muted">No projects found in this master resume.</p>
              ) : (
                <div className="curate-cards-list">
                  {sourceProjects.map((proj, idx) => {
                    const isSelected = selectedProjIndices.includes(idx);
                    const isMatched = isProjectMatched(proj, matchData);
                    const tech = formatTech(proj);
                    const desc = formatDesc(proj);
                    return (
                      <label
                        key={idx}
                        className={`curate-item-card ${isSelected ? "selected" : ""}`}
                        htmlFor={`proj-checkbox-${idx}`}
                      >
                        <div className="curate-checkbox-wrap">
                          <input
                            id={`proj-checkbox-${idx}`}
                            type="checkbox"
                            className="curate-checkbox"
                            checked={isSelected}
                            onChange={() => toggleProject(idx)}
                            aria-label={`Include ${proj.name || proj.title || "project"}`}
                          />
                        </div>
                        <div className="curate-card-content">
                          <div className="curate-card-header">
                            <strong className="curate-card-title">
                              {proj.name || proj.title || "Project"}
                            </strong>
                            {isMatched && (
                              <span className="curate-badge-match">
                                <CheckCircle2 size={12} />
                                <span>Relevant to job</span>
                              </span>
                            )}
                          </div>
                          {tech && (
                            <span className="curate-card-tech text-xs text-muted">{tech}</span>
                          )}
                          {desc && (
                            <p className="curate-card-desc text-xs text-secondary">{desc}</p>
                          )}
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {runError && (
              <div className="alert alert-error" style={{ marginTop: "var(--space-4)" }}>
                <AlertCircle size={16} />
                <span>{runError}</span>
              </div>
            )}

            <div className="modal-footer curation-footer" style={{ marginTop: "var(--space-6)" }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setStep("pick")}
              >
                Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={runTailor}
              >
                <Sparkles size={16} />
                <span>Generate Tailored Resume</span>
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: GENERATING */}
        {step === "loading" && (
          <div className="wizard-step-body text-center" style={{ padding: "var(--space-8) 0" }}>
            <div className="spinner-inline" style={{ margin: "0 auto var(--space-4)" }} />
            <h3>{t("tailor.loadingText", "Tailoring your resume...")}</h3>
            <p
              className="text-secondary text-sm"
              style={{ maxWidth: "420px", margin: "var(--space-2) auto 0" }}
            >
              {t(
                "tailor.loadingSub",
                "Optimizing your resume for this role while preserving your curated source records."
              )}
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}
