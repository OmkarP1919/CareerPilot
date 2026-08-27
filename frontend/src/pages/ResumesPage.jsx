import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
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
} from "lucide-react";

export default function ResumesPage() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [dragOver, setDragOver] = useState(false);

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

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

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
      notify("Resume uploaded and indexed successfully.");
    } catch (err) {
      notify(err.message || "Upload failed. Please try again.", "error");
    } finally {
      setUploading(false);
    }
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
                    </div>
                  </div>

                  <div className="resume-doc-actions">
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
    </div>
  );
}
