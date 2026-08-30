import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "./Modal";
import { api } from "../services/api";
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  Wand2,
} from "lucide-react";

function isResumeUsable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

function parsingStatusLabel(resume) {
  const status = resume.parsing_status || "pending";
  if (status === "completed" && !resume.parsing_error) return "Analyzed";
  if (status === "completed") return "Scanned / no text";
  if (status === "failed") return "Analysis failed";
  return "Pending analysis";
}

function parsingNote(resume) {
  const status = resume.parsing_status || "pending";
  if (status === "completed" && resume.parsing_error) {
    return "Image-based or unscannable";
  }
  if (resume.parsing_error) return "No usable text";
  if (status === "failed") return "Analysis failed";
  if (status === "pending" || status === "processing") return "Not analyzed yet";
  return "";
}

export default function TailoringModal({ job, isOpen, onClose, onSuccess }) {
  const [step, setStep] = useState("pick"); // pick | confirm | loading
  const [resumes, setResumes] = useState([]);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResume, setSelectedResume] = useState(null);
  const [runError, setRunError] = useState(null);

  const open = isOpen;

  const loadResumes = useCallback(async () => {
    setResumesLoading(true);
    setResumesError(null);
    setSelectedResume(null);
    setRunError(null);
    setStep("pick");
    try {
      const data = await api.get("/resumes");
      setResumes(Array.isArray(data) ? data : []);
      const firstUsable = (Array.isArray(data) ? data : []).find(isResumeUsable);
      if (firstUsable) setSelectedResume(firstUsable);
    } catch (err) {
      setResumesError(err.message || "Failed to load your resumes.");
    } finally {
      setResumesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadResumes();
    }
  }, [open, loadResumes]);

  const handleClose = () => {
    if (step === "loading") return; // don't allow closing mid-request
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

  const usableCount = resumes.filter(isResumeUsable).length;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Tailor My Resume">
      {step === "loading" ? (
        <div className="tailor-loading" role="status" aria-live="polite">
          <div className="spinner" />
          <p className="tailor-loading-title">Tailoring your resume...</p>
          <p className="tailor-loading-sub">
            Optimizing your resume for this role while preserving your actual
            experience.
          </p>
        </div>
      ) : step === "confirm" ? (
        <div className="tailor-confirm">
          <div className="tailor-confirm-card">
            <span className="tailor-confirm-label">Tailoring resume</span>
            <strong className="tailor-confirm-resume">{selectedResume?.original_filename}</strong>
          </div>
          <div className="tailor-confirm-row">
            <span className="tailor-confirm-label">For</span>
            <span className="tailor-confirm-job">
              {job?.title}
              {job?.company ? ` at ${job.company}` : ""}
            </span>
          </div>

          <div className="tailor-trust-note">
            <ShieldCheck size={15} />
            <span>
              Your original resume is unchanged. CareerPilot only uses
              information supported by your existing resume/profile.
            </span>
          </div>

          {runError && (
            <div className="alert alert-error" role="alert">
              <AlertCircle size={16} />
              <span>{runError}</span>
            </div>
          )}

          <div className="modal-footer-inline tailor-confirm-actions">
            <button className="btn btn-outline" onClick={() => setStep("pick")} type="button">
              <ArrowRight size={16} className="flip-h" />
              <span>Back</span>
            </button>
            <button className="btn btn-primary" onClick={runTailor} type="button">
              <Wand2 size={16} />
              <span>Tailor My Resume</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="tailor-pick">
          <p className="text-secondary tailor-pick-intro">
            Choose a resume to create a tailored version for{" "}
            <strong>{job?.title}</strong> at <strong>{job?.company}</strong>. This is
            separate from Resume Match.
          </p>

          {resumesLoading ? (
            <div className="resume-insights-loading">
              <div className="spinner" />
              <p>Loading resumes...</p>
            </div>
          ) : resumesError ? (
            <div className="resume-insight-error">
              <AlertCircle size={20} />
              <div>
                <strong>Could not load resumes.</strong>
                <p>{resumesError}</p>
              </div>
            </div>
          ) : resumes.length === 0 ? (
            <div className="resume-insight-empty">
              <FileText size={20} />
              <p>You have no uploaded resumes yet.</p>
              <Link to="/resumes" className="btn btn-primary btn-sm">
                <FileText size={14} />
                <span>Upload a Resume</span>
              </Link>
            </div>
          ) : usableCount === 0 ? (
            <div className="resume-insight-empty">
              <AlertCircle size={20} />
              <p>
                No usable resume found. Upload a text-based PDF resume before
                tailoring.
              </p>
              <Link to="/resumes" className="btn btn-primary btn-sm">
                <FileText size={14} />
                <span>Upload Resume</span>
              </Link>
            </div>
          ) : (
            <>
              <div className="resume-analyze-list" role="listbox" aria-label="Select a resume to tailor">
                {resumes.map((resume) => {
                  const usable = isResumeUsable(resume);
                  const isSelected = selectedResume?.id === resume.id;
                  return (
                    <button
                      key={resume.id}
                      type="button"
                      disabled={!usable}
                      onClick={() => setSelectedResume(resume)}
                      role="option"
                      aria-selected={isSelected}
                      className={`resume-analyze-option ${isSelected ? "is-selected" : ""} ${!usable ? "is-disabled" : ""}`}
                    >
                      <div className="resume-analyze-option-main">
                        <div className="resume-analyze-option-icon">
                          <FileText size={18} />
                        </div>
                        <div className="resume-analyze-option-details">
                          <strong className="resume-analyze-option-name">
                            {resume.original_filename}
                          </strong>
                          <span className={`parsing-status-chip parsing-${resume.parsing_status || "pending"}`}>
                            {resume.parsing_status === "completed" && !resume.parsing_error ? (
                              <CheckCircle2 size={12} />
                            ) : resume.parsing_status === "failed" ? (
                              <XCircle size={12} />
                            ) : (
                              <RefreshCw size={12} />
                            )}
                            <span>{parsingStatusLabel(resume)}</span>
                          </span>
                        </div>
                      </div>
                      {!usable && (
                        <span className="resume-analyze-option-note">{parsingNote(resume)}</span>
                      )}
                    </button>
                  );
                })}
              </div>

              {selectedResume && (
                <div className="modal-footer-inline">
                  <button
                    className="btn btn-outline btn-block"
                    onClick={proceedToConfirm}
                    type="button"
                  >
                    <ArrowRight size={16} />
                    <span>Continue</span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
