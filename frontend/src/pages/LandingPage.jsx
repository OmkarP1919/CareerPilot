import { useState } from "react";
import { Link } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import {
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Briefcase,
  Layers,
  FileText,
  Sparkles,
  ShieldCheck,
  Sun,
  Moon,
} from "lucide-react";

export default function LandingPage() {
  const { theme, setTheme } = useTheme();
  const [activeWorkflowStep, setActiveWorkflowStep] = useState("find");

  return (
    <div className="landing-page">
      {/* Sticky Header */}
      <header className="landing-header" aria-label="Landing page navigation">
        <nav className="landing-nav">
          <Link to="/" className="landing-logo" aria-label="CareerPilot AI">
            <span className="topnav-logo-mark">
              <span className="logo-dot" />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
          </Link>

          <div className="landing-nav-links">
            <a href="#workflow">How It Works</a>
            <a href="#preview">Product Preview</a>
          </div>

          <div className="landing-nav-actions">
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label="Toggle Theme"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign In
            </Link>
            <Link to="/signup" className="btn btn-primary btn-sm">
              <span>Get Started Free</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-inner">
          <div className="landing-badge">
            <Sparkles size={14} />
            <span>Intelligent Career Companion</span>
          </div>

          <h1 className="landing-hero-title">
            Find better jobs.
            <br />
            <span className="landing-hero-highlight">Apply with confidence.</span>
          </h1>

          <p className="landing-hero-subtitle">
            CareerPilot helps you discover relevant opportunities, understand your fit,
            tailor your resume safely, and manage your applications — all in one place.
          </p>

          <div className="landing-hero-actions">
            <Link to="/signup" className="btn btn-primary btn-lg">
              <span>Get Started Free</span>
              <ArrowRight size={18} />
            </Link>
            <a href="#workflow" className="btn btn-secondary btn-lg">
              <span>See How It Works</span>
            </a>
          </div>

          {/* Workflow Stepper Bar */}
          <div className="landing-stepper" id="workflow">
            <div className="stepper-item">
              <span className="stepper-num">1</span>
              <span className="stepper-label">Find Jobs</span>
            </div>
            <div className="stepper-arrow">→</div>
            <div className="stepper-item">
              <span className="stepper-num">2</span>
              <span className="stepper-label">Understand Fit</span>
            </div>
            <div className="stepper-arrow">→</div>
            <div className="stepper-item">
              <span className="stepper-num">3</span>
              <span className="stepper-label">Tailor Resume</span>
            </div>
            <div className="stepper-arrow">→</div>
            <div className="stepper-item">
              <span className="stepper-num">4</span>
              <span className="stepper-label">Track Applications</span>
            </div>
          </div>
        </div>
      </section>

      {/* Product Outcomes in Action (Realistic UI Demonstration) */}
      <section className="landing-showcase" id="preview">
        <div className="container">
          <div className="section-header text-center">
            <h2>Designed for your entire career journey</h2>
            <p>Every step gives you clarity, transparent fit analysis, and full control.</p>
          </div>

          {/* Interactive Step Switcher */}
          <div className="showcase-nav" role="tablist">
            <button
              className={`showcase-nav-btn ${activeWorkflowStep === "find" ? "active" : ""}`}
              onClick={() => setActiveWorkflowStep("find")}
              role="tab"
              aria-selected={activeWorkflowStep === "find"}
            >
              <Briefcase size={16} />
              <span>1. FIND</span>
            </button>
            <button
              className={`showcase-nav-btn ${activeWorkflowStep === "match" ? "active" : ""}`}
              onClick={() => setActiveWorkflowStep("match")}
              role="tab"
              aria-selected={activeWorkflowStep === "match"}
            >
              <Sparkles size={16} />
              <span>2. MATCH</span>
            </button>
            <button
              className={`showcase-nav-btn ${activeWorkflowStep === "tailor" ? "active" : ""}`}
              onClick={() => setActiveWorkflowStep("tailor")}
              role="tab"
              aria-selected={activeWorkflowStep === "tailor"}
            >
              <FileText size={16} />
              <span>3. TAILOR</span>
            </button>
            <button
              className={`showcase-nav-btn ${activeWorkflowStep === "apply" ? "active" : ""}`}
              onClick={() => setActiveWorkflowStep("apply")}
              role="tab"
              aria-selected={activeWorkflowStep === "apply"}
            >
              <Layers size={16} />
              <span>4. APPLY</span>
            </button>
          </div>

          {/* Showcase Display Area */}
          <div className="showcase-card">
            {activeWorkflowStep === "find" && (
              <div className="demo-step demo-find">
                <div className="demo-header">
                  <div>
                    <span className="demo-badge">Opportunity Discovery</span>
                    <h3 style={{ marginTop: "0.25rem" }}>Personalized recommendations based on your actual skills</h3>
                  </div>
                  <span className="demo-chip">12 new matches today</span>
                </div>

                <div className="demo-job-card">
                  <div className="demo-job-top">
                    <div>
                      <h4 className="demo-job-title">Backend Developer</h4>
                      <p className="demo-job-company">Stripe • Remote · Full-time · 0–2 years</p>
                    </div>
                    <div className="match-pill match-high">91% Match</div>
                  </div>

                  <div className="demo-job-skills">
                    <span className="skill-chip match">Python</span>
                    <span className="skill-chip match">FastAPI</span>
                    <span className="skill-chip match">PostgreSQL</span>
                    <span className="skill-chip match">Docker</span>
                  </div>

                  <div className="demo-job-match-summary">
                    <span className="match-point positive">
                      <CheckCircle2 size={14} className="text-success" />
                      <span>8 matching skills found in your profile</span>
                    </span>
                    <span className="match-point warning">
                      <AlertTriangle size={14} className="text-warning" />
                      <span>2 recommended skills to highlight</span>
                    </span>
                  </div>

                  <div className="demo-job-footer">
                    <span className="text-muted text-xs">Posted 2 days ago</span>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button className="btn btn-primary btn-sm" type="button">
                        View Opportunity
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeWorkflowStep === "match" && (
              <div className="demo-step demo-match">
                <div className="demo-header">
                  <div>
                    <span className="demo-badge">Fit Breakdown</span>
                    <h3 style={{ marginTop: "0.25rem" }}>Transparent 5-factor fit analysis</h3>
                  </div>
                  <div className="match-score-large">
                    <span className="score-num font-mono">91%</span>
                    <span className="score-text">Excellent Match</span>
                  </div>
                </div>

                <div className="demo-factor-bars">
                  <div className="factor-row">
                    <div className="factor-info">
                      <span>Skills Alignment</span>
                      <span className="font-mono">92%</span>
                    </div>
                    <div className="score-bar-track">
                      <div className="score-bar-fill" style={{ width: "92%", background: "var(--accent)" }} />
                    </div>
                  </div>

                  <div className="factor-row">
                    <div className="factor-info">
                      <span>Projects Relevance</span>
                      <span className="font-mono">84%</span>
                    </div>
                    <div className="score-bar-track">
                      <div className="score-bar-fill" style={{ width: "84%", background: "var(--accent)" }} />
                    </div>
                  </div>

                  <div className="factor-row">
                    <div className="factor-info">
                      <span>Experience Depth</span>
                      <span className="font-mono">76%</span>
                    </div>
                    <div className="score-bar-track">
                      <div className="score-bar-fill" style={{ width: "76%", background: "var(--accent)" }} />
                    </div>
                  </div>

                  <div className="factor-row">
                    <div className="factor-info">
                      <span>Role & Domain</span>
                      <span className="font-mono">90%</span>
                    </div>
                    <div className="score-bar-track">
                      <div className="score-bar-fill" style={{ width: "90%", background: "var(--accent)" }} />
                    </div>
                  </div>
                </div>

                <div className="demo-match-reasons">
                  <div className="reasons-box why-match">
                    <h5>Why You Match</h5>
                    <ul>
                      <li>✓ Strong Python & async API background</li>
                      <li>✓ Production project using PostgreSQL</li>
                      <li>✓ Aligns with target Backend Engineering path</li>
                    </ul>
                  </div>
                  <div className="reasons-box missing">
                    <h5>Missing / Recommended</h5>
                    <ul>
                      <li>⚠ Docker containerization experience</li>
                      <li>⚠ AWS cloud deployment experience</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {activeWorkflowStep === "tailor" && (
              <div className="demo-step demo-tailor">
                <div className="demo-header">
                  <div>
                    <span className="demo-badge">Safe Resume Tailoring</span>
                    <h3 style={{ marginTop: "0.25rem" }}>Before & After: Optimized without hallucination</h3>
                  </div>
                  <span className="demo-chip text-success">
                    <ShieldCheck size={14} />
                    <span>Original experience preserved</span>
                  </span>
                </div>

                <div className="demo-comparison-grid">
                  <div className="comparison-col original">
                    <div className="comparison-col-header">Original Bullet</div>
                    <p className="comparison-text">
                      "Built an internal API service for users to search database entries quickly."
                    </p>
                  </div>
                  <div className="comparison-arrow">→</div>
                  <div className="comparison-col tailored">
                    <div className="comparison-col-header">Tailored Bullet</div>
                    <p className="comparison-text">
                      "Engineered high-throughput REST API endpoints in <strong>FastAPI</strong> with indexed <strong>PostgreSQL</strong> queries, reducing search latency by 35%."
                    </p>
                  </div>
                </div>

                <div className="demo-keywords-summary">
                  <div className="keywords-group">
                    <span className="keywords-title">Keywords Highlighted:</span>
                    <span className="kw-tag success">FastAPI ✓</span>
                    <span className="kw-tag success">PostgreSQL ✓</span>
                    <span className="kw-tag success">REST API ✓</span>
                  </div>
                  <div className="keywords-group">
                    <span className="keywords-title">Not Added (Unsupported):</span>
                    <span className="kw-tag omitted">Docker ⚠</span>
                  </div>
                </div>
              </div>
            )}

            {activeWorkflowStep === "apply" && (
              <div className="demo-step demo-apply">
                <div className="demo-header">
                  <div>
                    <span className="demo-badge">Application Tracking</span>
                    <h3 style={{ marginTop: "0.25rem" }}>Organized pipeline from submission to offer</h3>
                  </div>
                  <span className="demo-chip">12 Active Submissions</span>
                </div>

                <div className="demo-pipeline-row">
                  <div className="pipeline-step done">
                    <span className="pip-num">1</span>
                    <span className="pip-label">Saved</span>
                  </div>
                  <div className="pipeline-step done">
                    <span className="pip-num">2</span>
                    <span className="pip-label">Applied</span>
                  </div>
                  <div className="pipeline-step active">
                    <span className="pip-num">3</span>
                    <span className="pip-label">Interview</span>
                  </div>
                  <div className="pipeline-step">
                    <span className="pip-num">4</span>
                    <span className="pip-label">Offer</span>
                  </div>
                </div>

                <div className="demo-app-list">
                  <div className="demo-app-item">
                    <div>
                      <strong>Backend Developer</strong> · Company XYZ
                      <div className="text-muted text-xs">Applied Aug 28 · Next follow-up: Sep 2</div>
                    </div>
                    <span className="status-badge status-interview">Interview Scheduled</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Trust & Ethics Guarantee */}
      <section className="landing-trust">
        <div className="container-narrow text-center">
          <ShieldCheck size={32} className="text-accent" style={{ margin: "0 auto var(--space-3)" }} />
          <h3>Honest, Safe & Private</h3>
          <p>
            CareerPilot never invents false credentials or alters your core career facts.
            Your resumes and application data are kept private in your personal workspace.
          </p>
          <div style={{ marginTop: "var(--space-6)" }}>
            <Link to="/signup" className="btn btn-primary btn-lg">
              <span>Create Your Free Account</span>
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="container">
          <div className="landing-footer-inner">
            <div className="landing-footer-brand">
              <span className="topnav-logo-mark">
                <span className="logo-dot" />
              </span>
              <span>CareerPilot AI</span>
            </div>
            <p className="text-muted text-xs">
              Intelligent Career Progression Platform. Designed for students and job seekers.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
