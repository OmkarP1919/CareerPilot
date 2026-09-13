import { useState, useEffect } from "react";
import Modal from "../Modal";
import { Save } from "lucide-react";

export default function ProfileRecordModal({
  isOpen,
  onClose,
  type, // "experience" | "project" | "education" | "certification"
  initialData = null,
  onSave,
}) {
  const [formData, setFormData] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    if (initialData) {
      setFormData({ ...initialData });
    } else {
      switch (type) {
        case "experience":
          setFormData({ company: "", role: "", start_date: "", end_date: "", description: "", technologies: "" });
          break;
        case "project":
          setFormData({ name: "", description: "", technologies: "", github_url: "", live_url: "" });
          break;
        case "education":
          setFormData({ degree: "", college: "", branch: "", graduation_year: "", cgpa: "" });
          break;
        case "certification":
          setFormData({ name: "", organization: "", issue_date: "", credential_url: "" });
          break;
        default:
          setFormData({});
      }
    }
  }, [isOpen, type, initialData]);

  if (!isOpen) return null;

  const isEdit = Boolean(initialData?.id);
  const titles = {
    experience: isEdit ? "Edit Work Experience" : "Add Work Experience",
    project: isEdit ? "Edit Featured Project" : "Add Featured Project",
    education: isEdit ? "Edit Education History" : "Add Education Record",
    certification: isEdit ? "Edit Certification" : "Add Certification",
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSave(formData);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Modal isOpen={isOpen} onClose={submitting ? () => {} : onClose} title={titles[type] || "Record"}>
      <form onSubmit={handleSubmit} className="profile-record-form">
        {/* Experience Fields */}
        {type === "experience" && (
          <>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-company">Company *</label>
                <input
                  id="rec-company"
                  className="form-input"
                  value={formData.company || ""}
                  onChange={(e) => updateField("company", e.target.value)}
                  placeholder="e.g. Stripe"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-role">Role Title *</label>
                <input
                  id="rec-role"
                  className="form-input"
                  value={formData.role || ""}
                  onChange={(e) => updateField("role", e.target.value)}
                  placeholder="e.g. Senior Backend Engineer"
                  required
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-start">Start Date</label>
                <input
                  id="rec-start"
                  className="form-input"
                  value={formData.start_date || ""}
                  onChange={(e) => updateField("start_date", e.target.value)}
                  placeholder="e.g. Jun 2023"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-end">End Date</label>
                <input
                  id="rec-end"
                  className="form-input"
                  value={formData.end_date || ""}
                  onChange={(e) => updateField("end_date", e.target.value)}
                  placeholder="e.g. Present"
                />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-exp-desc">Description / Accomplishments</label>
              <textarea
                id="rec-exp-desc"
                className="form-textarea"
                rows={3}
                value={formData.description || ""}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="Key contributions and achievements..."
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-exp-tech">Technologies</label>
              <input
                id="rec-exp-tech"
                className="form-input"
                value={formData.technologies || ""}
                onChange={(e) => updateField("technologies", e.target.value)}
                placeholder="e.g. Python, FastAPI, PostgreSQL, AWS"
              />
            </div>
          </>
        )}

        {/* Project Fields */}
        {type === "project" && (
          <>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-proj-name">Project Name *</label>
              <input
                id="rec-proj-name"
                className="form-input"
                value={formData.name || ""}
                onChange={(e) => updateField("name", e.target.value)}
                placeholder="e.g. Distributed Task Queue"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-proj-desc">Description</label>
              <textarea
                id="rec-proj-desc"
                className="form-textarea"
                rows={3}
                value={formData.description || ""}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="Problem solved, impact, and architectural decisions..."
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-proj-tech">Technologies Used</label>
              <input
                id="rec-proj-tech"
                className="form-input"
                value={formData.technologies || ""}
                onChange={(e) => updateField("technologies", e.target.value)}
                placeholder="e.g. React, Node.js, Redis, Docker"
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-proj-github">GitHub URL</label>
                <input
                  id="rec-proj-github"
                  className="form-input"
                  type="url"
                  value={formData.github_url || ""}
                  onChange={(e) => updateField("github_url", e.target.value)}
                  placeholder="https://github.com/..."
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-proj-live">Live Demo URL</label>
                <input
                  id="rec-proj-live"
                  className="form-input"
                  type="url"
                  value={formData.live_url || ""}
                  onChange={(e) => updateField("live_url", e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>
          </>
        )}

        {/* Education Fields */}
        {type === "education" && (
          <>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-edu-degree">Degree *</label>
                <input
                  id="rec-edu-degree"
                  className="form-input"
                  value={formData.degree || ""}
                  onChange={(e) => updateField("degree", e.target.value)}
                  placeholder="e.g. B.Tech, B.S., M.S."
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-edu-branch">Major / Branch</label>
                <input
                  id="rec-edu-branch"
                  className="form-input"
                  value={formData.branch || ""}
                  onChange={(e) => updateField("branch", e.target.value)}
                  placeholder="e.g. Computer Science"
                />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-edu-college">University / College *</label>
              <input
                id="rec-edu-college"
                className="form-input"
                value={formData.college || ""}
                onChange={(e) => updateField("college", e.target.value)}
                placeholder="e.g. University of California, Berkeley"
                required
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-edu-year">Graduation Year</label>
                <input
                  id="rec-edu-year"
                  className="form-input"
                  value={formData.graduation_year || ""}
                  onChange={(e) => updateField("graduation_year", e.target.value)}
                  placeholder="e.g. 2025"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-edu-cgpa">CGPA / GPA</label>
                <input
                  id="rec-edu-cgpa"
                  className="form-input"
                  value={formData.cgpa || ""}
                  onChange={(e) => updateField("cgpa", e.target.value)}
                  placeholder="e.g. 3.8 / 4.0"
                />
              </div>
            </div>
          </>
        )}

        {/* Certification Fields */}
        {type === "certification" && (
          <>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-cert-name">Certification Name *</label>
              <input
                id="rec-cert-name"
                className="form-input"
                value={formData.name || ""}
                onChange={(e) => updateField("name", e.target.value)}
                placeholder="e.g. AWS Certified Solutions Architect"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rec-cert-org">Issuing Organization</label>
              <input
                id="rec-cert-org"
                className="form-input"
                value={formData.organization || ""}
                onChange={(e) => updateField("organization", e.target.value)}
                placeholder="e.g. Amazon Web Services, Google Cloud"
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="rec-cert-date">Issue Date</label>
                <input
                  id="rec-cert-date"
                  className="form-input"
                  value={formData.issue_date || ""}
                  onChange={(e) => updateField("issue_date", e.target.value)}
                  placeholder="e.g. Jan 2025"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="rec-cert-url">Credential URL</label>
                <input
                  id="rec-cert-url"
                  className="form-input"
                  type="url"
                  value={formData.credential_url || ""}
                  onChange={(e) => updateField("credential_url", e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>
          </>
        )}

        <div className="form-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", marginTop: "var(--space-4)" }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            <Save size={16} aria-hidden="true" />
            <span>{submitting ? "Saving..." : isEdit ? "Save Changes" : "Add Entry"}</span>
          </button>
        </div>
      </form>
    </Modal>
  );
}
