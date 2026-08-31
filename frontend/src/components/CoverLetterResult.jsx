import { useState } from "react";
import { useTranslation } from "../context/LanguageContext";
import { useToast } from "./Toast";
import Badge from "./ui/Badge";
import {
  Copy,
  Check,
  RefreshCw,
  ArrowLeft,
  FileText,
  ShieldCheck,
} from "lucide-react";

function cleanText(letter) {
  if (letter && letter.content && typeof letter.content === "string" && letter.content.trim()) {
    return letter.content;
  }
  const sc = (letter && letter.structured_content) || {};
  return [sc.greeting, sc.opening, Array.isArray(sc.body_paragraphs) ? sc.body_paragraphs.join("\n\n") : "", sc.closing, sc.signature]
    .filter(Boolean)
    .join("\n\n");
}

export default function CoverLetterResult({ letter, onBack, onRegenerate, canRegenerate = true }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const sc = (letter && letter.structured_content) || {};
  const greeting = sc.greeting || "";
  const opening = sc.opening || "";
  const bodyParagraphs = Array.isArray(sc.body_paragraphs) ? sc.body_paragraphs : [];
  const closing = sc.closing || "";
  const signature = sc.signature || "";

  const supportedPoints = Array.isArray(letter?.supported_points)
    ? letter.supported_points
    : Array.isArray(sc.supported_points)
    ? sc.supported_points
    : [];
  const unsupported = Array.isArray(letter?.unsupported_requirements)
    ? letter.unsupported_requirements
    : Array.isArray(sc.unsupported_requirements)
    ? sc.unsupported_requirements
    : [];

  const handleCopy = async () => {
    const text = cleanText(letter);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(t("cover.copied", "Cover letter copied."));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(t("cover.copyFailed", "Couldn't copy the cover letter. Please try again."));
    }
  };

  const hasStructured = greeting || opening || bodyParagraphs.length > 0 || closing || signature;

  return (
    <div className="cover-result">
      {/* Actions */}
      <div className="cover-result-actions">
        {onBack && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>
            <ArrowLeft size={16} />
            <span>{t("cover.back", "Back")}</span>
          </button>
        )}
        <div className="cover-result-action-group">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            title={t("cover.accessibility.copy", "Copy cover letter to clipboard")}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? t("cover.copiedShort", "Copied") : t("cover.copy", "Copy Cover Letter")}</span>
          </button>
          {canRegenerate && onRegenerate && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={onRegenerate}>
              <RefreshCw size={16} />
              <span>{t("cover.generateAgain", "Generate Again")}</span>
            </button>
          )}
        </div>
      </div>

      {/* Document Preview */}
      <section className="card cover-doc-card">
        <div className="cover-doc-meta">
          <div className="state-badge">
            <FileText size={14} />
            <span>{t("cover.savedVersion", "Saved Version")}</span>
          </div>
          {letter?.created_at && (
            <span className="text-xs text-muted">
              {t("cover.createdOn", "Created")} {new Date(letter.created_at).toLocaleDateString()}
            </span>
          )}
          <div className="cover-provider">
            <Badge variant="outline">{letter?.ai_provider || "AI"}</Badge>
            {letter?.model && <Badge variant="outline">{letter.model}</Badge>}
          </div>
        </div>

        {hasStructured ? (
          <div className="cover-doc">
            <div className="cover-doc-body">
              {greeting && <p className="cover-paragraph">{greeting}</p>}
              {opening && <p className="cover-paragraph">{opening}</p>}
              {bodyParagraphs.map((p, i) => (
                <p key={i} className="cover-paragraph">
                  {typeof p === "string" ? p : p?.text || ""}
                </p>
              ))}
              {closing && <p className="cover-paragraph">{closing}</p>}
              {signature && <p className="cover-paragraph cover-signature">{signature}</p>}
            </div>
          </div>
        ) : (
          <div className="cover-doc">
            <div className="cover-doc-body">
              <p className="cover-paragraph">{cleanText(letter)}</p>
            </div>
          </div>
        )}

        {/* Why These Points */}
        {supportedPoints.length > 0 && (
          <div className="cover-insight-block">
            <h4>{t("cover.whyThesePoints", "WHY THESE POINTS")}</h4>
            <p className="text-xs text-secondary">{t("cover.supportedByExperience", "Supported by your experience")}</p>
            <ul className="cover-supported-list">
              {supportedPoints.map((pt, i) => (
                <li key={i}>
                  <Check size={16} className="text-success" />
                  <span>{typeof pt === "string" ? pt : pt?.text || pt?.point || ""}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Not Added */}
        {unsupported.length > 0 && (
          <div className="cover-insight-block cover-notadded">
            <h4>{t("cover.notAdded", "NOT ADDED")}</h4>
            <p className="text-xs text-warning">{t("cover.notAddedExpl", "These requirements were not included because they were not supported by the information in your resume/profile.")}</p>
            <ul className="cover-notadded-list">
              {unsupported.map((req, i) => (
                <li key={i}>
                  <span>{typeof req === "string" ? req : req?.requirement || req?.text || ""}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Trust banner */}
        <div className="cover-trust-banner">
          <ShieldCheck size={18} className="text-success" />
          <span>{t("cover.trustDetail", "CareerPilot uses information from your resume/profile and the job description. Unsupported qualifications are not added.")}</span>
        </div>
      </section>
    </div>
  );
}
