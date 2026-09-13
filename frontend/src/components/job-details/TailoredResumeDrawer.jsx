import { useEffect } from "react";
import TailoredResult from "../TailoredResult";
import { X } from "lucide-react";

export default function TailoredResumeDrawer({
  isOpen,
  onClose,
  result,
  job,
  existingScore,
  onRegenerate,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    if (isOpen) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  if (!isOpen || !result) return null;

  return (
    <div className="tailored-drawer-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="tailored-drawer-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="tailored-drawer-header">
          <span className="drawer-title">Tailored Resume Preview</span>
          <button
            type="button"
            className="btn btn-ghost btn-icon btn-sm drawer-close-btn"
            onClick={onClose}
            aria-label="Close Preview"
          >
            <X size={18} />
          </button>
        </div>

        <div className="tailored-drawer-body">
          <TailoredResult
            result={result}
            job={job}
            existingMatchScore={existingScore}
            onBack={onClose}
            onRegenerate={onRegenerate}
          />
        </div>
      </div>
    </div>
  );
}
