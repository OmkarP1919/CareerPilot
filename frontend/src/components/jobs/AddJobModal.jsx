import { useState } from "react";
import Modal from "../Modal";
import { api } from "../../services/api";
import { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS } from "./JobFilterDrawer";

const EMPTY_FORM = {
  title: "",
  company: "",
  location: "",
  employment_type: "Full-time",
  experience_level: "Entry Level",
  required_skills: "",
  description: "",
  application_url: "",
};

export default function AddJobModal({ isOpen, onClose, onJobAdded, notify }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) {
      notify?.("Please provide both job title and company.", "error");
      return;
    }

    setSubmitting(true);
    try {
      const skillsArray = form.required_skills
        ? form.required_skills.split(",").map((s) => s.trim()).filter(Boolean)
        : [];

      const res = await api.post("/jobs/", {
        title: form.title.trim(),
        company: form.company.trim(),
        location: form.location.trim() || null,
        employment_type: form.employment_type || null,
        experience_level: form.experience_level || null,
        description: form.description.trim() || null,
        required_skills: skillsArray.length > 0 ? skillsArray.join(", ") : null,
        application_url: form.application_url.trim() || null,
        source: "Target Role",
      });

      notify?.("Target role added successfully.");
      setForm(EMPTY_FORM);
      onJobAdded?.(res);
      onClose();
    } catch {
      notify?.("Failed to add target role. Please try again.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Target Role">
      <form onSubmit={handleSubmit} className="stack" style={{ gap: "var(--space-4)" }}>
        <div className="form-group">
          <label className="form-label" htmlFor="custom-role-title">
            Job Title *
          </label>
          <input
            id="custom-role-title"
            type="text"
            className="form-input"
            placeholder="e.g. Senior Backend Engineer"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="custom-role-company">
            Company *
          </label>
          <input
            id="custom-role-company"
            type="text"
            className="form-input"
            placeholder="e.g. Datadog"
            value={form.company}
            onChange={(e) => setForm({ ...form, company: e.target.value })}
            required
          />
        </div>

        <div className="drawer-grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="custom-role-location">
              Location
            </label>
            <input
              id="custom-role-location"
              type="text"
              className="form-input"
              placeholder="e.g. Remote or Pune"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custom-role-type">
              Job Type
            </label>
            <select
              id="custom-role-type"
              className="form-select"
              value={form.employment_type}
              onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
            >
              {EMPLOYMENT_TYPES.map((tVal) => (
                <option key={tVal} value={tVal}>
                  {tVal}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="drawer-grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="custom-role-level">
              Experience Level
            </label>
            <select
              id="custom-role-level"
              className="form-select"
              value={form.experience_level}
              onChange={(e) => setForm({ ...form, experience_level: e.target.value })}
            >
              {EXPERIENCE_LEVELS.map((lVal) => (
                <option key={lVal} value={lVal}>
                  {lVal}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custom-role-url">
              Application URL
            </label>
            <input
              id="custom-role-url"
              type="url"
              className="form-input"
              placeholder="https://..."
              value={form.application_url}
              onChange={(e) => setForm({ ...form, application_url: e.target.value })}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="custom-role-skills">
            Required Skills (comma separated)
          </label>
          <input
            id="custom-role-skills"
            type="text"
            className="form-input"
            placeholder="e.g. Python, FastAPI, PostgreSQL, Docker"
            value={form.required_skills}
            onChange={(e) => setForm({ ...form, required_skills: e.target.value })}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="custom-role-desc">
            Role Description
          </label>
          <textarea
            id="custom-role-desc"
            className="form-textarea"
            rows={4}
            placeholder="Paste role description or key requirements..."
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>

        <div className="modal-footer" style={{ marginTop: "var(--space-2)" }}>
          <button
            className="btn btn-ghost"
            type="button"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Adding Role..." : "Add Target Role"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
