import { useState, useEffect, useCallback } from "react";
import { Plus, History, CalendarClock, Link2 } from "lucide-react";
import { api } from "../../services/api";
import {
  USER_EVENT_TYPES,
  EVENT_LABELS,
  INTERVIEW_KIND_LABELS,
  INTERVIEW_STATUS_LABELS,
  DOCUMENT_TYPE_LABELS,
  formatDateTime,
} from "./pipelineUtils";

export default function PipelineTimelineTab({ applicationId, notify }) {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [eventType, setEventType] = useState("note_added");
  const [eventNotes, setEventNotes] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.getApplicationTimeline(applicationId);
      setEntries(Array.isArray(data?.entries) ? data.entries : []);
    } catch {
      setError("Couldn't load activity timeline for this application.");
      setEntries([]);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAddEvent = async (e) => {
    e.preventDefault();
    if (!eventNotes.trim()) {
      notify("Please add a note for this activity.", "error");
      return;
    }
    setAdding(true);
    try {
      await api.createApplicationEvent(applicationId, {
        event_type: eventType,
        notes: eventNotes.trim(),
      });
      notify("Event logged to timeline.");
      setEventNotes("");
      load();
    } catch (err) {
      notify(err?.message || "Couldn't record timeline event.", "error");
    } finally {
      setAdding(false);
    }
  };

  const renderTitle = (entry) => {
    if (entry.kind === "event") {
      if (entry.event_type === "status_changed" && entry.metadata) {
        const from = entry.metadata.from_status || "Unknown";
        const to = entry.metadata.to_status || "Unknown";
        return (
          <span className="tl-title">
            {EVENT_LABELS[entry.event_type] || entry.event_type}: {from} → {to}
          </span>
        );
      }
      return <span className="tl-title">{EVENT_LABELS[entry.event_type] || entry.event_type}</span>;
    }
    if (entry.kind === "interview") {
      return (
        <span className="tl-title">
          {INTERVIEW_KIND_LABELS[entry.interview_kind] || entry.interview_kind} Interview
        </span>
      );
    }
    return (
      <span className="tl-title">
        {DOCUMENT_TYPE_LABELS[entry.document_type] || entry.document_type}
        {entry.name ? `: ${entry.name}` : ""}
      </span>
    );
  };

  return (
    <div className="pipeline-tab-panel pipeline-timeline-tab">
      {/* Activity Log Form */}
      <form className="card pipeline-inline-form" onSubmit={handleAddEvent}>
        <h4 className="pipeline-section-title">
          <Plus size={15} aria-hidden="true" />
          <span>Log Activity or Milestone</span>
        </h4>
        <div className="form-row">
          <div className="form-group" style={{ flex: "0 0 160px" }}>
            <label htmlFor="pipeline-event-type-select" className="form-label">
              Activity Type
            </label>
            <select
              id="pipeline-event-type-select"
              className="form-select"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            >
              {USER_EVENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {EVENT_LABELS[type] || type}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label htmlFor="pipeline-event-notes-input" className="form-label">
              Note
            </label>
            <input
              id="pipeline-event-notes-input"
              className="form-input"
              placeholder="e.g. Sent follow-up email to hiring manager"
              value={eventNotes}
              onChange={(e) => setEventNotes(e.target.value)}
            />
          </div>
        </div>
        <div className="pipeline-form-actions">
          <button type="submit" className="btn btn-secondary btn-sm" disabled={adding}>
            {adding ? "Logging..." : "Add to Timeline"}
          </button>
        </div>
      </form>

      {/* Timeline entries */}
      {error && <p className="pipeline-panel-error text-danger">{error}</p>}

      {entries === null ? (
        <div className="pipeline-loading-text text-muted">Loading timeline...</div>
      ) : entries.length === 0 ? (
        <div className="pipeline-inline-empty card">
          <History size={28} aria-hidden="true" />
          <p>No activity logged yet. Add your first note above.</p>
        </div>
      ) : (
        <div className="pipeline-timeline-list card">
          {entries.map((entry, idx) => {
            const kind = entry.kind || "event";

            return (
              <div key={entry.id || idx} className="pipeline-timeline-item">
                <span className={`tl-dot tl-dot-${kind}`} aria-hidden="true" />
                <div className="tl-content">
                  <div className="tl-main">
                    {renderTitle(entry)}
                    {entry.notes && <p className="tl-notes">{entry.notes}</p>}
                    {entry.kind === "interview" && (
                      <p className="tl-meta">
                        <CalendarClock size={12} aria-hidden="true" />
                        <span>
                          {formatDateTime(entry.scheduled_at)} ·{" "}
                          {INTERVIEW_STATUS_LABELS[entry.status] || entry.status}
                        </span>
                      </p>
                    )}
                    {entry.kind === "document" && entry.source_resume_id && (
                      <p className="tl-meta">
                        <Link2 size={12} aria-hidden="true" />
                        <span>Linked to your resume</span>
                      </p>
                    )}
                  </div>
                  <span className="tl-time">{formatDateTime(entry.created_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
