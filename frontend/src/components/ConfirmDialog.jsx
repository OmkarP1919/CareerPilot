import { useEffect, useCallback, useRef } from "react";
import { X, AlertTriangle } from "lucide-react";

export default function ConfirmDialog({
  isOpen = false,
  open,
  onClose,
  onCancel,
  onConfirm,
  title = "Confirm Action",
  message,
  description,
  children,
  confirmLabel = "Confirm",
  confirmText,
  cancelLabel = "Cancel",
  cancelText,
  destructive = false,
  variant,
  loading = false,
}) {
  const visible = isOpen || Boolean(open);
  const handleClose = onClose || onCancel || (() => {});
  const resolvedConfirmLabel = confirmText || confirmLabel;
  const resolvedCancelLabel = cancelText || cancelLabel;
  const isDestructive = destructive || variant === "destructive";
  const contentText = message || description;

  const dialogRef = useRef(null);
  const cancelBtnRef = useRef(null);
  const previousFocus = useRef(null);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Escape") {
        if (!loading) {
          handleClose();
        }
        return;
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    },
    [handleClose, loading]
  );

  useEffect(() => {
    if (visible) {
      previousFocus.current = document.activeElement;
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
      requestAnimationFrame(() => {
        // Focus the cancel button first for safety, especially on destructive actions
        if (cancelBtnRef.current) {
          cancelBtnRef.current.focus();
        } else if (dialogRef.current) {
          const first = dialogRef.current.querySelector(
            'button:not([disabled]), [tabindex]:not([tabindex="-1"])'
          );
          if (first) first.focus();
        }
      });
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
      if (previousFocus.current && previousFocus.current.focus) {
        previousFocus.current.focus();
      }
    };
  }, [visible, handleKeyDown]);

  if (!visible) return null;

  return (
    <div
      className="modal-overlay"
      onClick={() => {
        if (!loading) handleClose();
      }}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
    >
      <div
        className="modal confirm-dialog-modal"
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "440px" }}
      >
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            {isDestructive && (
              <AlertTriangle
                size={20}
                className="text-danger"
                aria-hidden="true"
                style={{ flexShrink: 0 }}
              />
            )}
            <h3 id="confirm-dialog-title">{title}</h3>
          </div>
          <button
            className="modal-close-btn"
            onClick={() => {
              if (!loading) handleClose();
            }}
            disabled={loading}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body" id="confirm-dialog-description">
          {contentText && (
            <p style={{ margin: 0, color: "var(--text-secondary)", lineHeight: "var(--leading-relaxed)" }}>
              {contentText}
            </p>
          )}
          {children}
        </div>

        <div className="modal-footer">
          <button
            ref={cancelBtnRef}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleClose}
            disabled={loading}
          >
            {resolvedCancelLabel}
          </button>
          <button
            type="button"
            className={`btn btn-sm ${isDestructive ? "btn-danger" : "btn-primary"}`}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-inline" aria-hidden="true" />
                <span>Processing...</span>
              </>
            ) : (
              resolvedConfirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
