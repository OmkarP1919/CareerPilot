import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTranslation } from "../context/LanguageContext";
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Sparkles,
  FileText,
  User,
  Compass,
  X,
} from "lucide-react";

export default function OnboardingModal({ isOpen, onClose, profileData, resumesCount = 0 }) {
  const { currentUser } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (!isOpen) return null;

  const hasName = Boolean(currentUser?.displayName || profileData?.full_name);
  const hasResume = resumesCount > 0;
  const hasSkills = Array.isArray(profileData?.skills) && profileData.skills.length > 0;
  const hasExperienceOrProjects =
    (Array.isArray(profileData?.experiences) && profileData.experiences.length > 0) ||
    (Array.isArray(profileData?.projects) && profileData.projects.length > 0);
  const hasRole = Boolean(profileData?.target_title || profileData?.headline);

  const steps = [
    {
      id: "profile",
      label: "Basic profile & target role",
      done: hasName && hasRole,
      link: "/profile",
      desc: "Add your headline and career goals.",
    },
    {
      id: "resume",
      label: "Upload your original resume",
      done: hasResume,
      link: "/resumes",
      desc: "PDF parsing extracts your experience automatically.",
    },
    {
      id: "skills",
      label: "Add your core technical skills",
      done: hasSkills,
      link: "/profile",
      desc: "Powers precise job matching.",
    },
    {
      id: "projects",
      label: "Add projects or work experience",
      done: hasExperienceOrProjects,
      link: "/profile",
      desc: "Strengthens your role fit score.",
    },
    {
      id: "discover",
      label: "Find your first tailored opportunities",
      done: false,
      link: "/discover",
      desc: "Discover roles matching your exact background.",
    },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  const nextStep = steps.find((s) => !s.done) || steps[0];

  const handleContinue = () => {
    onClose();
    navigate(nextStep.link);
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="modal-container onboarding-modal">
        <div className="modal-header">
          <div className="onboarding-badge">
            <Sparkles size={14} />
            <span>Welcome to CareerPilot</span>
          </div>
          <button
            className="btn btn-ghost btn-icon btn-sm"
            onClick={onClose}
            aria-label="Skip onboarding for now"
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body onboarding-body">
          <h2 id="onboarding-title" className="onboarding-heading">
            Let's get you job-ready
          </h2>
          <p className="onboarding-sub">
            Complete a few quick steps so CareerPilot can find the most relevant opportunities and match your skills accurately.
          </p>

          <div className="onboarding-progress-wrap">
            <div className="onboarding-progress-header">
              <span className="progress-label">Profile Readiness</span>
              <span className="progress-value font-mono">{progressPercent}%</span>
            </div>
            <div className="score-bar-track">
              <div
                className="score-bar-fill"
                style={{ width: `${Math.max(10, progressPercent)}%`, background: "var(--accent)" }}
              />
            </div>
          </div>

          <div className="onboarding-steps-list">
            {steps.map((step, idx) => (
              <div key={step.id} className={`onboarding-step-item ${step.done ? "done" : ""}`}>
                <div className="step-icon-wrap">
                  {step.done ? (
                    <CheckCircle2 size={18} className="text-success" />
                  ) : (
                    <Circle size={18} className="text-tertiary" />
                  )}
                </div>
                <div className="step-content">
                  <div className="step-title">{step.label}</div>
                  <div className="step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer onboarding-footer">
          <button className="btn btn-ghost" onClick={onClose} type="button">
            Skip for now
          </button>
          <button className="btn btn-primary" onClick={handleContinue} type="button">
            <span>Continue Setup</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
