import { useState, useEffect, useCallback, useRef } from "react";
import { Link2, CloudUpload, FileText, Trash2 } from "lucide-react";
import { api } from "../../services/api";
import ConfirmDialog from "../ConfirmDialog";
import {
  DOCUMENT_TYPES,
  DOCUMENT_TYPE_LABELS,
  formatFileSize,
  formatFriendlyDate,
} from "./pipelineUtils";

export default function PipelineDocumentsTab({ applicationId, notify }) {
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [attachForm, setAttachForm] = useState({
    source_resume_id: "",
    document_type: "resume",
    name: "",
  });
  const [attaching, setAttaching] = useState(false);
  const [uploadType, setUploadType] = useState("resume");
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [docs, resumeData] = await Promise.all([
        api.getApplicationDocuments(applicationId),
        api.get("/resumes").catch(() => []),
      ]);
      const resumeList = Array.isArray(resumeData) ? resumeData : [];
      setDocuments(Array.isArray(docs) ? docs : []);
      setResumes(resumeList);
      setAttachForm((f) => {
        if (f.source_resume_id) return f;
        const usable = resumeList.find((r) => r.parsing_status === "completed" && !r.parsing_error);
        return { ...f, source_resume_id: usable ? usable.id : resumeList[0]?.id || "" };
      });
    } catch {
      setError("Couldn't load documents for this application.");
      setDocuments([]);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAttach = async (e) => {
    e.preventDefault();
    if (!attachForm.source_resume_id) {
      notify("Select a resume to attach.", "error");
      return;
    }
    setAttaching(true);
    try {
      await api.attachApplicationDocument(applicationId, {
        source_resume_id: attachForm.source_resume_id,
        document_type: attachForm.document_type,
        name: attachForm.name.trim() || null,
      });
      notify("Document attached.");
      setAttachForm((f) => ({ ...f, name: "" }));
      load();
    } catch (err) {
      notify(err?.message || "Couldn't update documents.", "error");
    } finally {
      setAttaching(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      notify("Choose a file to upload.", "error");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("document_type", uploadType);
      if (uploadName.trim()) {
        form.append("name", uploadName.trim());
      }
      await api.uploadApplicationDocument(applicationId, form);
      notify("Document uploaded.");
      setUploadName("");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err) {
      notify(err?.message || "Couldn't upload file.", "error");
    } finally {
      setUploading(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteApplicationDocument(applicationId, deleteTarget.id);
      notify("Document detached from application.");
      setDeleteTarget(null);
      load();
    } catch (err) {
      notify(err?.message || "Failed to remove document.", "error");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="pipeline-tab-panel pipeline-documents-tab">
      {/* Existing documents */}
      <div className="pipeline-tab-panel-header">
        <h4 className="pipeline-section-title">Attached Materials</h4>
      </div>

      {error && <p className="pipeline-panel-error text-danger">{error}</p>}

      {documents === null ? (
        <div className="pipeline-loading-text text-muted">Loading documents...</div>
      ) : documents.length === 0 ? (
        <div className="pipeline-inline-empty card">
          <FileText size={28} aria-hidden="true" />
          <p>No documents attached yet. Attach an existing resume or upload files below.</p>
        </div>
      ) : (
        <div className="pipeline-docs-list card">
          {documents.map((doc) => (
            <div key={doc.id} className="pipeline-doc-item">
              <div className="doc-item-icon">
                <FileText size={18} aria-hidden="true" />
              </div>
              <div className="doc-item-details">
                <span className="doc-name">{doc.name || doc.original_filename || "Document"}</span>
                <div className="doc-meta">
                  <span className="doc-type-badge">
                    {DOCUMENT_TYPE_LABELS[doc.document_type] || doc.document_type}
                  </span>
                  {doc.file_size && <span>• {formatFileSize(doc.file_size)}</span>}
                  <span>• {formatFriendlyDate(doc.created_at)}</span>
                </div>
              </div>
              <div className="doc-item-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm text-danger"
                  onClick={() => setDeleteTarget(doc)}
                  title="Remove document"
                  aria-label="Remove document"
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Attach / Upload forms */}
      <div className="pipeline-docs-forms-grid">
        {/* Attach Existing Resume */}
        <form className="card pipeline-card-block" onSubmit={handleAttach}>
          <h4 className="pipeline-block-title">
            <Link2 size={14} aria-hidden="true" />
            <span>Attach Existing Resume</span>
          </h4>
          <div className="form-group">
            <label htmlFor="pipeline-doc-source-resume" className="form-label">
              Choose Resume
            </label>
            <select
              id="pipeline-doc-source-resume"
              className="form-select"
              value={attachForm.source_resume_id}
              onChange={(e) => setAttachForm((f) => ({ ...f, source_resume_id: e.target.value }))}
            >
              <option value="">—</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.original_filename || r.filename || "Untitled resume"}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="pipeline-doc-attach-type" className="form-label">
                Type
              </label>
              <select
                id="pipeline-doc-attach-type"
                className="form-select"
                value={attachForm.document_type}
                onChange={(e) => setAttachForm((f) => ({ ...f, document_type: e.target.value }))}
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {DOCUMENT_TYPE_LABELS[dt] || dt}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="pipeline-doc-attach-name" className="form-label">
                Label (optional)
              </label>
              <input
                id="pipeline-doc-attach-name"
                className="form-input"
                placeholder="e.g. Tailored version"
                value={attachForm.name}
                onChange={(e) => setAttachForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>
          <div className="pipeline-form-actions">
            <button type="submit" className="btn btn-secondary btn-sm" disabled={attaching}>
              {attaching ? "Attaching..." : "Attach Resume"}
            </button>
          </div>
        </form>

        {/* Upload New Document */}
        <form className="card pipeline-card-block" onSubmit={handleUpload}>
          <h4 className="pipeline-block-title">
            <CloudUpload size={14} aria-hidden="true" />
            <span>Upload New Document</span>
          </h4>
          <div className="form-group">
            <label htmlFor="pipeline-doc-upload-file" className="form-label">
              Choose File (.pdf, .docx)
            </label>
            <input
              id="pipeline-doc-upload-file"
              ref={fileRef}
              type="file"
              className="form-input"
              accept=".pdf,.docx"
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="pipeline-doc-upload-type" className="form-label">
                Type
              </label>
              <select
                id="pipeline-doc-upload-type"
                className="form-select"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {DOCUMENT_TYPE_LABELS[dt] || dt}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="pipeline-doc-upload-name" className="form-label">
                Label (optional)
              </label>
              <input
                id="pipeline-doc-upload-name"
                className="form-input"
                placeholder="e.g. Offer Letter"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
              />
            </div>
          </div>
          <div className="pipeline-form-actions">
            <button type="submit" className="btn btn-secondary btn-sm" disabled={uploading}>
              {uploading ? "Uploading..." : "Upload File"}
            </button>
          </div>
        </form>
      </div>

      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => !deleting && setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Remove Document"
        message="Remove this application document? Your original resume will not be affected."
        confirmLabel="Remove"
        cancelLabel="Cancel"
        destructive
        loading={deleting}
      />
    </div>
  );
}
