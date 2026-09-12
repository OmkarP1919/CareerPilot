import { Link } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import {
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  Briefcase,
  Layers,
  FileText,
  Sparkles,
  Sun,
  Moon,
  Lock,
  Compass,
  BarChart3,
  Check,
} from "lucide-react";

export default function LandingPage() {
  const { theme, setTheme } = useTheme();

  const handleToggleTheme = () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <div className="landing-page">
      {/* Sticky Header */}
      <header className="landing-header" aria-label="Main Navigation">
        <nav className="landing-nav">
          <Link to="/" className="landing-logo" aria-label="CareerPilot Home">
            <span className="landing-logo-mark">
              <span className="landing-logo-dot" />
            </span>
            <span className="landing-logo-text">CareerPilot</span>
          </Link>

          <div className="landing-nav-links">
            <a href="#preview">Product Preview</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#principles">Our Principles</a>
          </div>

          <div className="landing-nav-actions">
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm landing-theme-toggle"
              onClick={handleToggleTheme}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <Link to="/login" className="btn btn-ghost btn-sm landing-nav-login">
              Sign In
            </Link>
            <Link to="/signup" className="btn btn-primary btn-sm landing-nav-cta">
              <span>Get Started Free</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="landing-hero" aria-labelledby="hero-title">
        <div className="landing-hero-inner">
          <div className="landing-badge">
            <Sparkles size={13} />
            <span>Honest, Outcome-Driven Career Platform</span>
          </div>

          <h1 id="hero-title" className="landing-hero-title">
            Find the right role.
            <br />
            <span className="landing-hero-highlight">Apply with complete clarity.</span>
          </h1>

          <p className="landing-hero-subtitle">
            CareerPilot brings your job search into one calm workspace. Discover verified opportunities, understand your exact match fit, tailor your resume without fabricated claims, and track applications from submission to offer.
          </p>

          <div className="landing-hero-actions">
            <Link to="/signup" className="btn btn-primary btn-lg landing-hero-btn-primary">
              <span>Get Started Free</span>
              <ArrowRight size={16} />
            </Link>
            <a href="#preview" className="btn btn-secondary btn-lg landing-hero-btn-secondary">
              <span>See the Workflow</span>
            </a>
          </div>

          <div className="landing-hero-trust-bar">
            <span className="trust-item">
              <Check size={14} className="text-success" />
              <span>Transparent 5-factor scoring</span>
            </span>
            <span className="trust-dot">•</span>
            <span className="trust-item">
              <ShieldCheck size={14} className="text-accent" />
              <span>Zero hallucinated experience</span>
            </span>
            <span className="trust-dot">•</span>
            <span className="trust-item">
              <Check size={14} className="text-success" />
              <span>Private personal workspace</span>
            </span>
          </div>
        </div>
      </section>

      {/* Connected Workflow Preview (Static, Unified Canvas: Job -> Match -> Tailoring -> Pipeline) */}
      <section className="landing-preview-section" id="preview" aria-labelledby="preview-heading">
        <div className="landing-container">
          <div className="landing-section-header text-center">
            <span className="landing-section-kicker">Unified Experience</span>
            <h2 id="preview-heading">From discovery to offer in four connected steps</h2>
            <p className="landing-section-desc">
              Instead of switching between disconnected job boards, resume editors, and spreadsheets, CareerPilot connects the entire job search lifecycle into a single, cohesive workflow.
            </p>
          </div>

          {/* Workflow Canvas */}
          <div className="workflow-canvas">
            <div className="workflow-canvas-header">
              <div className="workflow-canvas-tabs">
                <span className="workflow-status-dot" />
                <span className="workflow-canvas-title">Live Candidate Pipeline Walkthrough</span>
              </div>
              <span className="workflow-illustrative-pill">Representative Preview</span>
            </div>

            <div className="workflow-stages-grid">
              {/* Stage 1: Target Opportunity */}
              <div className="workflow-stage-card">
                <div className="stage-card-header">
                  <div className="stage-card-meta">
                    <span className="stage-step-badge">1. Opportunity</span>
                    <span className="stage-tag verified">Verified Role</span>
                  </div>
                  <h3 className="stage-card-title">Backend Engineer</h3>
                  <p className="stage-card-sub">Stripe • Remote (US/EU) • Full-Time</p>
                </div>

                <div className="stage-card-body">
                  <div className="stage-spec-row">
                    <span className="stage-spec-label">Compensation</span>
                    <span className="stage-spec-val font-mono">$135,000 – $160,000</span>
                  </div>
                  <div className="stage-spec-row">
                    <span className="stage-spec-label">Experience</span>
                    <span className="stage-spec-val">Mid-Level (2–4 yrs)</span>
                  </div>

                  <div className="stage-skills-box">
                    <span className="stage-micro-label">Required Skills</span>
                    <div className="stage-skill-pills">
                      <span className="stage-pill matched">Python</span>
                      <span className="stage-pill matched">FastAPI</span>
                      <span className="stage-pill matched">PostgreSQL</span>
                      <span className="stage-pill missing">Docker</span>
                    </div>
                  </div>
                </div>

                <div className="stage-card-footer">
                  <span className="stage-footer-note text-accent">Role saved to your pipeline</span>
                </div>
              </div>

              {/* Stage 2: Transparent Fit Breakdown */}
              <div className="workflow-stage-card stage-card-featured">
                <div className="stage-card-header">
                  <div className="stage-card-meta">
                    <span className="stage-step-badge">2. Fit Analysis</span>
                    <span className="stage-tag high-fit">Strong Fit</span>
                  </div>
                  <div className="stage-score-display">
                    <span className="stage-score-value font-mono">89%</span>
                    <span className="stage-score-label">Overall Match Score</span>
                  </div>
                </div>

                <div className="stage-card-body">
                  <div className="stage-factors-list">
                    <div className="stage-factor-item">
                      <div className="stage-factor-meta">
                        <span>Skills Alignment</span>
                        <span className="font-mono">92%</span>
                      </div>
                      <div className="score-bar-track">
                        <div className="score-bar-fill" style={{ width: "92%", background: "var(--accent)" }} />
                      </div>
                    </div>
                    <div className="stage-factor-item">
                      <div className="stage-factor-meta">
                        <span>Project Relevance</span>
                        <span className="font-mono">86%</span>
                      </div>
                      <div className="score-bar-track">
                        <div className="score-bar-fill" style={{ width: "86%", background: "var(--accent)" }} />
                      </div>
                    </div>
                    <div className="stage-factor-item">
                      <div className="stage-factor-meta">
                        <span>Experience Depth</span>
                        <span className="font-mono">88%</span>
                      </div>
                      <div className="score-bar-track">
                        <div className="score-bar-fill" style={{ width: "88%", background: "var(--accent)" }} />
                      </div>
                    </div>
                  </div>

                  <div className="stage-fit-callout">
                    <CheckCircle2 size={13} className="text-success flex-shrink-0" />
                    <span>7 matching skills found. Recommended to emphasize REST API query optimization.</span>
                  </div>
                </div>

                <div className="stage-card-footer">
                  <span className="stage-footer-note text-success">Fit breakdown verified against target job</span>
                </div>
              </div>

              {/* Stage 3: Safe Resume Tailoring */}
              <div className="workflow-stage-card">
                <div className="stage-card-header">
                  <div className="stage-card-meta">
                    <span className="stage-step-badge">3. Resume Tailoring</span>
                    <span className="stage-tag fact-check">Safe AI</span>
                  </div>
                  <h3 className="stage-card-title">Targeted Alignment</h3>
                  <p className="stage-card-sub">Fact-preserving bullet enhancement</p>
                </div>

                <div className="stage-card-body">
                  <div className="stage-diff-box">
                    <div className="stage-diff-before">
                      <span className="diff-tag">Original Resume</span>
                      <p className="diff-text">"Built backend endpoints for searching database records quickly."</p>
                    </div>
                    <div className="stage-diff-after">
                      <span className="diff-tag tailored">Tailored Version</span>
                      <p className="diff-text">
                        "Engineered high-throughput REST API endpoints in <strong>FastAPI</strong> with indexed <strong>PostgreSQL</strong> queries, reducing search latency by 35%."
                      </p>
                    </div>
                  </div>

                  <div className="stage-tailor-assurance">
                    <ShieldCheck size={14} className="text-accent flex-shrink-0" />
                    <span>0 fabricated metrics or skills. Only true experience rephrased for ATS impact.</span>
                  </div>
                </div>

                <div className="stage-card-footer">
                  <span className="stage-footer-note text-muted">Ready to export to PDF / DOCX</span>
                </div>
              </div>

              {/* Stage 4: Application Pipeline */}
              <div className="workflow-stage-card">
                <div className="stage-card-header">
                  <div className="stage-card-meta">
                    <span className="stage-step-badge">4. Application Pipeline</span>
                    <span className="stage-tag pipeline-active">Active</span>
                  </div>
                  <h3 className="stage-card-title">Live Tracking</h3>
                  <p className="stage-card-sub">Application status & follow-up</p>
                </div>

                <div className="stage-card-body">
                  <div className="pipeline-mini-stepper">
                    <div className="mini-step completed">
                      <span className="mini-step-dot" />
                      <span className="mini-step-text">Saved</span>
                    </div>
                    <div className="mini-step-connector completed" />
                    <div className="mini-step completed">
                      <span className="mini-step-dot" />
                      <span className="mini-step-text">Tailored</span>
                    </div>
                    <div className="mini-step-connector completed" />
                    <div className="mini-step completed">
                      <span className="mini-step-dot" />
                      <span className="mini-step-text">Applied</span>
                    </div>
                    <div className="mini-step-connector current" />
                    <div className="mini-step current">
                      <span className="mini-step-dot" />
                      <span className="mini-step-text">Interview</span>
                    </div>
                  </div>

                  <div className="pipeline-mini-card">
                    <div className="mini-card-top">
                      <span className="mini-card-company">Stripe</span>
                      <span className="status-badge status-interview">Interview</span>
                    </div>
                    <p className="mini-card-role">Backend Engineer • Tailored v2</p>
                    <div className="mini-card-meta">
                      <span>Technical Screen scheduled for Tuesday</span>
                    </div>
                  </div>
                </div>

                <div className="stage-card-footer">
                  <span className="stage-footer-note text-muted">Follow-up reminder set automatically</span>
                </div>
              </div>
            </div>

            <div className="workflow-canvas-footer">
              <span className="canvas-footer-caption">
                * Illustrative demonstration of CareerPilot workflow. Actual match scores and tailoring suggestions are personalized to your uploaded resume and specific target jobs.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* How CareerPilot Works (4 Concise Steps) */}
      <section className="landing-how-section" id="how-it-works" aria-labelledby="how-heading">
        <div className="landing-container">
          <div className="landing-section-header text-center">
            <span className="landing-section-kicker">Structured Process</span>
            <h2 id="how-heading">How CareerPilot works for you</h2>
            <p className="landing-section-desc">
              A straightforward four-step process built to minimize job search burnout and maximize relevant interview invitations.
            </p>
          </div>

          <div className="landing-steps-grid">
            <div className="landing-step-item">
              <div className="landing-step-number">01</div>
              <div className="landing-step-icon-wrap">
                <Briefcase size={20} />
              </div>
              <h3 className="landing-step-title">Find the right opportunities</h3>
              <p className="landing-step-body">
                Discover curated opportunities aligned with your verified tech stack, target titles, and compensation preferences without wading through irrelevant postings.
              </p>
            </div>

            <div className="landing-step-item">
              <div className="landing-step-number">02</div>
              <div className="landing-step-icon-wrap">
                <BarChart3 size={20} />
              </div>
              <h3 className="landing-step-title">Understand your fit</h3>
              <p className="landing-step-body">
                See a transparent 5-factor breakdown explaining exactly why you match and pinpointing the precise skills or project context to highlight before applying.
              </p>
            </div>

            <div className="landing-step-item">
              <div className="landing-step-number">03</div>
              <div className="landing-step-icon-wrap">
                <FileText size={20} />
              </div>
              <h3 className="landing-step-title">Tailor your resume safely</h3>
              <p className="landing-step-body">
                Refine bullet points and optimize keywords for ATS scanners while strictly preserving your authentic experience with zero hallucinated credentials.
              </p>
            </div>

            <div className="landing-step-item">
              <div className="landing-step-number">04</div>
              <div className="landing-step-icon-wrap">
                <Layers size={20} />
              </div>
              <h3 className="landing-step-title">Track your pipeline</h3>
              <p className="landing-step-body">
                Keep every opportunity organized from initial save to final offer with milestone tracking, follow-up deadlines, and linked tailored resume versions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Trust & Product Principles */}
      <section className="landing-principles-section" id="principles" aria-labelledby="principles-heading">
        <div className="landing-container">
          <div className="landing-section-header text-center">
            <span className="landing-section-kicker">Core Principles</span>
            <h2 id="principles-heading">Built on honesty, precision, and privacy</h2>
            <p className="landing-section-desc">
              Job applications represent your professional reputation. We treat that responsibility with utmost seriousness.
            </p>
          </div>

          <div className="landing-principles-grid">
            <div className="landing-principle-card">
              <div className="principle-icon-circle">
                <ShieldCheck size={22} className="text-accent" />
              </div>
              <h3 className="principle-title">Fact-Preserving AI</h3>
              <p className="principle-text">
                CareerPilot never invents false job titles, fabricates certifications, or inserts skills you have not verified. Your resume reflects your genuine experience, articulated with impact.
              </p>
            </div>

            <div className="landing-principle-card">
              <div className="principle-icon-circle">
                <CheckCircle2 size={22} className="text-accent" />
              </div>
              <h3 className="principle-title">Transparent Match Scoring</h3>
              <p className="principle-text">
                No black-box mystery numbers. We show you the exact weighted factors — skills match, experience depth, and project alignment — so you know why you fit every opportunity.
              </p>
            </div>

            <div className="landing-principle-card">
              <div className="principle-icon-circle">
                <Lock size={22} className="text-accent" />
              </div>
              <h3 className="principle-title">Private Personal Workspace</h3>
              <p className="principle-text">
                Your resumes, interview notes, and application records belong solely to you. We do not sell user data to recruiters or train open models on your private employment history.
              </p>
            </div>

            <div className="landing-principle-card">
              <div className="principle-icon-circle">
                <Compass size={22} className="text-accent" />
              </div>
              <h3 className="principle-title">Unified Workflow</h3>
              <p className="principle-text">
                Eliminate the chaos of juggling 5 different browser tabs, text files, and spreadsheets. From discovery to offer, manage your entire search in one calm, dedicated workspace.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="landing-cta-section" aria-labelledby="cta-heading">
        <div className="landing-container-narrow">
          <div className="landing-cta-card">
            <h2 id="cta-heading" className="landing-cta-title">
              Ready to apply with confidence?
            </h2>
            <p className="landing-cta-subtitle">
              Join thousands of job seekers taking the guesswork out of their career progression. Free to start, no credit card required.
            </p>
            <div className="landing-cta-buttons">
              <Link to="/signup" className="btn btn-primary btn-lg landing-cta-primary-btn">
                <span>Create Your Free Account</span>
                <ArrowRight size={18} />
              </Link>
            </div>
            <p className="landing-cta-micro">
              Takes less than 2 minutes • Import your existing resume anytime
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer" aria-label="Site Footer">
        <div className="landing-container">
          <div className="landing-footer-top">
            <div className="landing-footer-brand-col">
              <Link to="/" className="landing-logo" aria-label="CareerPilot Home">
                <span className="landing-logo-mark">
                  <span className="landing-logo-dot" />
                </span>
                <span className="landing-logo-text">CareerPilot</span>
              </Link>
              <p className="landing-footer-tagline">
                Intelligent, transparent career progression platform for ambitious job seekers.
              </p>
            </div>

            <div className="landing-footer-links-col">
              <span className="landing-footer-col-title">Product</span>
              <a href="#preview">Product Preview</a>
              <a href="#how-it-works">How It Works</a>
              <a href="#principles">Our Principles</a>
            </div>

            <div className="landing-footer-links-col">
              <span className="landing-footer-col-title">Account</span>
              <Link to="/login">Sign In</Link>
              <Link to="/signup">Create Free Account</Link>
            </div>
          </div>

          <div className="landing-footer-bottom">
            <p className="landing-footer-copy">
              © {new Date().getFullYear()} CareerPilot AI. All rights reserved.
            </p>
            <div className="landing-footer-status">
              <span className="status-indicator-dot" />
              <span>All Systems Operational</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
