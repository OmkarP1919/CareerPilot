import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "./Modal";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

function isResumeUsable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

export default function TailoringModal({ job, isOpen, onClose, onSuccess }) {
  const { t } = useTranslation();
  const [step, setStep] = useState("pick"); // "pick" | "confirm" | "loading"
  const [resumes, setResumes] = useState([]);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResume, setSelectedResume] = useState(null);
  const [runError, setRunError] = useState(null);

  const loadResumes = useCallback(async () => {
    setResumesLoading(true);
    setResumesError(null);
    setSelectedResume(null);
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

  const proceedToConfirm = () => {
    if (!selectedResume) return;
    setRunError(null);
    setStep("confirm");
  };

  const runTailor = async () => {
    if (!selectedResume) return;
    setRunError(null);
    setStep("loading");
    try {
      const result = await api.tailorResume(job.id, selectedResume.id, false);
      onSuccess(result);
    } catch (err) {
      setRunError(err.message || "Resume tailoring could not be completed.");
      setStep("confirm");
    }
  };

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
            1. {t("tailor.step1", "Choose Resume")}
          </span>
          <span className="wizard-sep">→</span>
          <span className={`wizard-step ${step === "confirm" ? "active" : step === "loading" ? "done" : ""}`}>
            2. {t("tailor.step2", "Confirm")}
          </span>
          <span className="wizard-sep">→</span>
          <span className={`wizard-step ${step === "loading" ? "active" : ""}`}>
            3. {t("tailor.step3", "Tailoring")}
          </span>
        </div>

        {/* STEP 1: CHOOSE RESUME */}
        {step === "pick" && (
          <div className="wizard-step-body">
            <p className="text-secondary text-sm">
              Select the master resume you wish to tailor for <strong>{job.title}</strong> at{" "}
              <strong>{job.company}</strong>:
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
                      className={`resume-pick-item ${selectedResume?.id === r.id ? "selected" : ""} ${
                        !usable ? "disabled" : ""
                      }`}
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

            <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
              <button type="button" className="btn btn-ghost" onClick={handleClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={proceedToConfirm}
                disabled={!selectedResume}
              >
                <span>Continue</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: CONFIRM */}
        {step === "confirm" && (
          <div className="wizard-step-body">
            <div className="confirm-summary-box">
              <div className="confirm-row">
                <span className="confirm-label">Source Resume:</span>
                <strong>{selectedResume?.filename}</strong>
              </div>
              <div className="confirm-row">
                <span className="confirm-label">Target Role:</span>
                <strong>{job.title}</strong>
              </div>
              <div className="confirm-row">
                <span className="confirm-label">Company:</span>
                <strong>{job.company}</strong>
              </div>
            </div>

            <div className="trust-callout">
              <ShieldCheck size={18} className="text-success" />
              <div>
                <strong>Ethical AI Guarantee</strong>
                <p>
                  CareerPilot only optimizes phrasing and aligns keywords supported by your actual experience. We never invent fake degrees, jobs, or unsupported credentials.
                </p>
              </div>
            </div>

            {runError && (
              <div className="alert alert-error" style={{ marginTop: "var(--space-4)" }}>
                <AlertCircle size={16} />
                <span>{runError}</span>
              </div>
            )}

            <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
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
                <span>Start Tailoring</span>
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: TAILORING (Honest, calm loading state) */}
        {step === "loading" && (
          <div className="wizard-step-body text-center" style={{ padding: "var(--space-8) 0" }}>
            <div className="spinner-inline" style={{ margin: "0 auto var(--space-4)" }} />
            <h3>{t("tailor.loadingText", "Tailoring your resume...")}</h3>
            <p className="text-secondary text-sm" style={{ maxWidth: "420px", margin: "var(--space-2) auto 0" }}>
              {t(
                "tailor.loadingSub",
                "Optimizing your resume for this role while preserving your actual experience."
              )}
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}
