import { useRef, useState } from "react";
import { AlertCircle, Check, FileText, Loader2, Upload } from "lucide-react";
import Modal from "../Modal";
import { api } from "../../services/api";
import {
  buildResumeProfileDiff,
  applyResumeProfileSync,
  filterProfileDiff,
} from "./profileAutofillUtils";

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const CATEGORIES = [
  { key: "skills", label: "Skills" },
  { key: "experiences", label: "Experience" },
  { key: "projects", label: "Projects" },
  { key: "education", label: "Education" },
  { key: "certifications", label: "Certifications" },
  { key: "location", label: "Location" },
];

export default function FillProfileFromResumeModal({ isOpen, onClose, profile, onApplied }) {
  const fileInputRef = useRef(null);
  const [phase, setPhase] = useState("upload");
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState(null);
  const [diff, setDiff] = useState(null);
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);

  if (!isOpen) return null;

  const reset = () => {
    setDragging(false);
    setFileName("");
    setError(null);
    setDiff(null);
    setSelected([]);
    setResult(null);
  };

  const close = () => {
    reset();
    setPhase("upload");
    onClose();
  };

  const validateFile = (file) => {
    if (!file) return "No file selected. Please choose a PDF to upload.";
    const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name || "");
    if (!isPdf) return "Please upload a PDF file.";
    if (file.size > MAX_FILE_SIZE) return "File is too large. Maximum size is 10 MB.";
    return null;
  };

  const handleFile = async (file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setFileName(file.name);
    setPhase("uploading");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const created = await api.uploadFile("/resumes", formData);
      const resumeId = created?.id || created?.data?.id;
      if (!resumeId) throw new Error("Upload did not return a resume record.");

      let parsedData = null;
      try {
        const parsedRes = await api.get(`/resumes/${resumeId}/parsed`);
        parsedData = parsedRes?.data || null;
      } finally {
        api.delete(`/resumes/${resumeId}`).catch(() => {});
      }

      if (!parsedData || Object.keys(parsedData).length === 0) {
        setPhase("upload");
        setError("No usable information could be extracted from this resume. Please try a different PDF.");
        return;
      }

      const fullDiff = buildResumeProfileDiff(parsedData, profile);
      if (!fullDiff.hasChanges) {
        setPhase("upload");
        setError("Your profile already contains everything found in this resume. Nothing new to add.");
        return;
      }

      setDiff(fullDiff);
      setSelected(CATEGORIES.filter((c) => fullDiff.counts[c.key] > 0).map((c) => c.key));
      setPhase("review");
    } catch (err) {
      setPhase("upload");
      setError(err?.message || "Failed to process the resume. Please try again.");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer?.files?.[0]);
  };

  const toggleCategory = (key) => {
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const handleApply = async () => {
    const filteredDiff = filterProfileDiff(diff, selected);
    if (!filteredDiff.hasChanges) {
      setError("Select at least one category to import.");
      return;
    }
    setError(null);
    setPhase("applying");
    const applied = await applyResumeProfileSync(filteredDiff, api, profile);
    setResult(applied);
    setPhase("done");
    if (typeof onApplied === "function") onApplied();
  };

  const totalItems = selected.reduce((sum, key) => sum + (diff?.counts?.[key] || 0), 0);

  const renderPreview = () => {
    const showSkills = selected.includes("skills") && diff.toAdd.skills.length > 0;
    const showExperience = selected.includes("experiences") && diff.toAdd.experiences.length > 0;
    const showProjects = selected.includes("projects") && diff.toAdd.projects.length > 0;
    const showEducation = selected.includes("education") && diff.toAdd.education.length > 0;
    const showCerts = selected.includes("certifications") && diff.toAdd.certifications.length > 0;
    const showLocation = selected.includes("location") && Boolean(diff.toAdd.location);

    if (!showSkills && !showExperience && !showProjects && !showEducation && !showCerts && !showLocation) {
      return null;
    }

    return (
      <details className="fill-preview">
        <summary className="fill-preview-summary">
          <span>Preview extracted information</span>
        </summary>
        <div className="fill-preview-body">
          {showLocation && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Location</span>
              <p className="fill-preview-location">{diff.toAdd.location}</p>
            </div>
          )}
          {showSkills && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Skills</span>
              <div className="sync-tags-wrap">
                {diff.toAdd.skills.slice(0, 10).map((s) => (
                  <span key={s.name} className="profile-skill-chip">
                    {s.name}
                  </span>
                ))}
                {diff.toAdd.skills.length > 10 && (
                  <span className="text-xs text-muted">+{diff.toAdd.skills.length - 10} more</span>
                )}
              </div>
            </div>
          )}
          {showExperience && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Experience</span>
              <ul className="sync-simple-list">
                {diff.toAdd.experiences.slice(0, 8).map((exp, idx) => (
                  <li key={idx}>
                    <strong>{exp.role}</strong> at {exp.company}
                  </li>
                ))}
                {diff.toAdd.experiences.length > 8 && (
                  <li className="text-muted">+{diff.toAdd.experiences.length - 8} more</li>
                )}
              </ul>
            </div>
          )}
          {showProjects && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Projects</span>
              <ul className="sync-simple-list">
                {diff.toAdd.projects.slice(0, 8).map((proj, idx) => (
                  <li key={idx}>{proj.name}</li>
                ))}
                {diff.toAdd.projects.length > 8 && (
                  <li className="text-muted">+{diff.toAdd.projects.length - 8} more</li>
                )}
              </ul>
            </div>
          )}
          {showEducation && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Education</span>
              <ul className="sync-simple-list">
                {diff.toAdd.education.slice(0, 8).map((edu, idx) => (
                  <li key={idx}>
                    <strong>{edu.degree}</strong> — {edu.college}
                  </li>
                ))}
                {diff.toAdd.education.length > 8 && (
                  <li className="text-muted">+{diff.toAdd.education.length - 8} more</li>
                )}
              </ul>
            </div>
          )}
          {showCerts && (
            <div className="sync-detail-group">
              <span className="sync-detail-title">Certifications</span>
              <ul className="sync-simple-list">
                {diff.toAdd.certifications.slice(0, 8).map((cert, idx) => (
                  <li key={idx}>{cert.name}</li>
                ))}
                {diff.toAdd.certifications.length > 8 && (
                  <li className="text-muted">+{diff.toAdd.certifications.length - 8} more</li>
                )}
              </ul>
            </div>
          )}
        </div>
      </details>
    );
  };

  const hasErrors = phase === "done" && result && result.errors?.length > 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={phase === "uploading" || phase === "applying" ? () => {} : close}
      title="Fill Profile from Resume"
      wide
    >
      <div className="fill-modal-body">
        {phase === "upload" && (
          <>
            <div
              className={`fill-dropzone${dragging ? " dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="fill-file-input"
                aria-label="Choose a PDF resume to upload"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                  e.target.value = "";
                }}
              />
              <div className="fill-dropzone-icon">
                <Upload size={24} aria-hidden="true" />
              </div>
              <p className="fill-dropzone-title">Drag & drop your resume here</p>
              <p className="fill-dropzone-hint">PDF up to 10 MB</p>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileText size={15} aria-hidden="true" />
                Browse Files
              </button>
            </div>
            {error && (
              <div className="fill-error" role="alert">
                <AlertCircle size={16} aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}
          </>
        )}

        {phase === "uploading" && (
          <div className="fill-spinner-row" role="status" aria-live="polite">
            <Loader2 size={18} className="animate-spin" aria-hidden="true" />
            <span>Uploading and parsing {fileName}...</span>
          </div>
        )}

        {phase === "review" && (
          <>
            <div className="fill-review-intro">
              <p className="text-secondary text-sm">
                Review the information extracted from <strong>{fileName}</strong>. Select what to add.
                Existing profile data will be preserved and duplicates will be skipped.
              </p>
            </div>

            <div className="fill-category-list" role="group" aria-label="Information to import">
              {CATEGORIES.map((cat) => {
                const count = diff.counts[cat.key] || 0;
                if (count === 0) return null;
                const isSelected = selected.includes(cat.key);
                return (
                  <label key={cat.key} className="fill-category-option">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleCategory(cat.key)}
                    />
                    <span className="fill-category-meta">
                      <span className="fill-category-name">{cat.label}</span>
                      <span className="fill-category-count">
                        {cat.key === "location"
                          ? "Current base location"
                          : `${count} item${count === 1 ? "" : "s"} to add`}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>

            {renderPreview()}
          </>
        )}

        {phase === "applying" && (
          <div className="fill-spinner-row" role="status" aria-live="polite">
            <Loader2 size={18} className="animate-spin" aria-hidden="true" />
            <span>Adding items to your profile...</span>
          </div>
        )}

        {phase === "done" && (
          <div className={`fill-done${hasErrors ? " partial" : ""}`}>
            {hasErrors ? (
              <AlertCircle size={22} className="text-danger" aria-hidden="true" />
            ) : (
              <Check size={22} className="text-success" aria-hidden="true" />
            )}
            <p className="fill-done-title">
              {hasErrors ? "Imported with some issues" : "Profile updated!"}
            </p>
            <p className="fill-done-subtext">
              {result.count > 0
                ? `${result.count} item${result.count === 1 ? "" : "s"} were added to your profile.`
                : "No items were added."}
              {hasErrors && ` ${result.errors[0]}`}
            </p>
          </div>
        )}

        {(phase === "upload" || phase === "review") && (
          <div className="fill-actions">
            {phase === "upload" && (
              <button type="button" className="btn btn-secondary" onClick={close}>
                Cancel
              </button>
            )}
            {phase === "review" && (
              <>
                <button type="button" className="btn btn-secondary" onClick={close}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleApply}
                  disabled={totalItems === 0}
                >
                  <Check size={16} aria-hidden="true" />
                  <span>
                    Import {totalItems} Item{totalItems === 1 ? "" : "s"}
                  </span>
                </button>
              </>
            )}
          </div>
        )}

        {phase === "done" && (
          <div className="fill-actions">
            <button type="button" className="btn btn-primary" onClick={close}>
              Close
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}