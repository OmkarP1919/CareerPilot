import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "./Modal";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import CoverLetterResult from "./CoverLetterResult";
import {
  ShieldCheck,
  Sparkles,
  ArrowRight,
  AlertCircle,
  Eye,
} from "lucide-react";

function isResumeUsable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

function errorMessageFor(err, t) {
  const status = err?.status;
  const kind = err?.kind;
  if (kind === "network") {
    return t("cover.errNetwork", "Couldn't connect to CareerPilot. Check your connection and try again.");
  }
  if (kind === "timeout" || status === 504) {
    return t("cover.err504", "Generating the cover letter took too long. Please try again.");
  }
  if (status === 503) {
    return t("cover.err503", "Cover letter generation is temporarily unavailable. Please try again.");
  }
  if (status === 502) {
    return t("cover.err502", "We couldn't validate the generated cover letter. Please try again.");
  }
  if (status === 409) {
    return t("cover.err409", "Your resume is still being processed. Please try again in a moment.");
  }
  if (status === 422) {
    return t("cover.err422", "We couldn't create a cover letter from this resume yet.");
  }
  if (status === 429) {
    return t("cover.err429", "Too many requests right now. Please wait a moment and try again.");
  }
  return t("cover.errGeneric", "Something went wrong. Please try again.");
}

export default function CoverLetterModal({
  job,
  isOpen,
  onClose,
  onSuccess,
  viewOnly = false,
  initialLetter = null,
}) {
  const { t } = useTranslation();

  // viewOnly mode shows an already-generated letter directly (Resumes / Pipeline)
  const [step, setStep] = useState(viewOnly && initialLetter ? "result" : "pick");

  const [resumes, setResumes] = useState([]);
  const [existingByResume, setExistingByResume] = useState({});
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResume, setSelectedResume] = useState(null);

  const [letter, setLetter] = useState(initialLetter || null);
  const [runError, setRunError] = useState(null);

  const reset = useCallback(() => {
    setStep(viewOnly && initialLetter ? "result" : "pick");
    setRunError(null);
    setLetter(initialLetter || null);
  }, [viewOnly, initialLetter]);

  const loadResumes = useCallback(async () => {
    setResumesLoading(true);
    setResumesError(null);
    setSelectedResume(null);
    setRunError(null);
    try {
      const data = await api.get("/resumes");
      const list = Array.isArray(data) ? data : [];
      setResumes(list);

      // Look up existing cover letters to offer "View Existing"
      let existing = {};
      try {
        const letters = await api.getCoverLetters();
        if (Array.isArray(letters)) {
          existing = {};
          letters.forEach((cl) => {
            if (cl.job_id === job.id && cl.source_resume_id) {
              existing[cl.source_resume_id] = cl;
            }
          });
        }
      } catch {
        // Non-fatal: just don't offer "View Existing"
      }
      setExistingByResume(existing);

      const firstExisting = list.find((r) => isResumeUsable(r) && existing[r.id]);
      const firstUsable = list.find(isResumeUsable);
      setSelectedResume(firstExisting || firstUsable || null);
    } catch (err) {
      setResumesError(err.message || "Failed to load uploaded resumes.");
    } finally {
      setResumesLoading(false);
    }
  }, [job.id]);

  useEffect(() => {
    if (isOpen) {
      reset();
      if (!(viewOnly && initialLetter)) {
        loadResumes();
      }
    }
  }, [isOpen, reset, loadResumes, viewOnly, initialLetter]);

  const handleClose = () => {
    if (step === "loading") return;
    onClose();
  };

  const proceedToConfirm = () => {
    if (!selectedResume) return;
    setRunError(null);
    setStep("confirm");
  };

  const viewExisting = () => {
    if (!selectedResume || !existingByResume[selectedResume.id]) return;
    setLetter(existingByResume[selectedResume.id]);
    setStep("result");
  };

  const runGenerate = async (regenerate = false) => {
    if (!selectedResume) return;
    setRunError(null);
    setStep("loading");
    try {
      const result = await api.generateCoverLetter(job.id, selectedResume.id, regenerate);
      setLetter(result);
      setStep("result");
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setRunError(errorMessageFor(err, t));
      setStep("confirm");
    }
  };

  const hasUsable = resumes.some(isResumeUsable);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      wide
      title={t("cover.title", "Write Cover Letter")}
    >
      {/* viewOnly result mode */}
      {step === "result" && letter ? (
        <CoverLetterResult
          letter={letter}
          onBack={() => {
            if (viewOnly) {
              reset();
              onClose();
            } else {
              setStep("pick");
            }
          }}
          onRegenerate={() => runGenerate(true)}
          canRegenerate={!viewOnly}
        />
      ) : (
        <div className="tailoring-wizard">
          {/* Step indicator */}
          <div className="wizard-steps-header">
            <span className={`wizard-step ${step === "pick" ? "active" : "done"}`}>
              1. {t("cover.step1", "Choose Resume")}
            </span>
            <span className="wizard-sep">→</span>
            <span className={`wizard-step ${step === "confirm" ? "active" : step === "loading" ? "done" : ""}`}>
              2. {t("cover.step2", "Review")}
            </span>
            <span className="wizard-sep">→</span>
            <span className={`wizard-step ${step === "loading" ? "active" : ""}`}>
              3. {t("cover.step3", "Writing")}
            </span>
          </div>

          {/* STEP 1: CHOOSE RESUME */}
          {step === "pick" && (
            <div className="wizard-step-body">
              <p className="text-secondary text-sm">
                {t("cover.chooseFor", "Select the resume your cover letter will be based on for")}{" "}
                <strong>{job.title}</strong> — <strong>{job.company}</strong>:
              </p>

              {resumesLoading ? (
                <div className="loading-state">
                  <div className="spinner-inline" />
                  <p>{t("cover.loadingResumes", "Loading resumes...")}</p>
                </div>
              ) : resumesError ? (
                <div className="alert alert-error">
                  <AlertCircle size={16} />
                  <span>{resumesError}</span>
                </div>
              ) : resumes.length === 0 || !hasUsable ? (
                <div className="empty-resumes-prompt">
                  <p>{t("cover.noUsableResume", "Upload a text-based PDF resume to create a cover letter.")}</p>
                  <Link to="/resumes" className="btn btn-primary btn-sm">
                    {t("cover.uploadResume", "Upload Resume")}
                  </Link>
                </div>
              ) : (
                <div className="resumes-pick-list">
                  {resumes.map((r) => {
                    const usable = isResumeUsable(r);
                    const hasExisting = Boolean(existingByResume[r.id]);
                    return (
                      <label
                        key={r.id}
                        className={`resume-pick-item ${selectedResume?.id === r.id ? "selected" : ""} ${
                          !usable ? "disabled" : ""
                        }`}
                      >
                        <input
                          type="radio"
                          name="cover_resume_pick"
                          disabled={!usable}
                          checked={selectedResume?.id === r.id}
                          onChange={() => setSelectedResume(r)}
                        />
                        <div className="pick-info">
                          <strong>{r.filename}</strong>
                          <span className="text-xs text-muted">
                            {!usable
                              ? t("cover.parsingPending", "Still processing")
                              : hasExisting
                              ? t("cover.alreadyCreated", "Cover letter already created")
                              : t("cover.usableReady", "Ready for cover letter")}
                          </span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}

              {selectedResume && existingByResume[selectedResume.id] && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm cover-view-existing"
                  style={{ marginTop: "var(--space-3)" }}
                  onClick={viewExisting}
                >
                  <Eye size={16} />
                  <span>{t("cover.viewExisting", "View Existing Cover Letter")}</span>
                </button>
              )}

              <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
                <button type="button" className="btn btn-ghost" onClick={handleClose}>
                  {t("cover.cancel", "Cancel")}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={proceedToConfirm}
                  disabled={!selectedResume}
                >
                  <span>{t("cover.continue", "Continue")}</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: CONFIRM / REVIEW */}
          {step === "confirm" && (
            <div className="wizard-step-body">
              <div className="confirm-summary-box">
                <div className="confirm-row">
                  <span className="confirm-label">{t("cover.job", "JOB")}</span>
                  <strong>
                    {job.title} · {job.company}
                  </strong>
                </div>
                <div className="confirm-row">
                  <span className="confirm-label">{t("cover.resume", "RESUME")}</span>
                  <strong>{selectedResume?.filename}</strong>
                </div>
              </div>

              <div className="trust-callout">
                <ShieldCheck size={18} className="text-success" />
                <div>
                  <strong>{t("cover.trustRealExperience", "Built from your real experience")}</strong>
                  <p>{t("cover.trustText", "Your cover letter will be based only on information from your resume/profile and this job. CareerPilot will not invent qualifications or experience.")}</p>
                </div>
              </div>

              {runError && (
                <div className="alert alert-error" style={{ marginTop: "var(--space-4)" }}>
                  <AlertCircle size={16} />
                  <span>{runError}</span>
                </div>
              )}

              <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
                <button type="button" className="btn btn-ghost" onClick={() => setStep("pick")}>
                  {t("cover.back", "Back")}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => runGenerate(false)}
                >
                  <Sparkles size={16} />
                  <span>{t("cover.generate", "Generate Cover Letter")}</span>
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: WRITING (calm loading state) */}
          {step === "loading" && (
            <div className="wizard-step-body text-center" style={{ padding: "var(--space-8) 0" }}>
              <div className="spinner-inline" style={{ margin: "0 auto var(--space-4)" }} />
              <h3>{t("cover.loadingText", "Writing your cover letter...")}</h3>
              <p className="text-secondary text-sm" style={{ maxWidth: "420px", margin: "var(--space-2) auto 0" }}>
                {t("cover.loadingSub", "Connecting your experience to this opportunity.")}
              </p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
