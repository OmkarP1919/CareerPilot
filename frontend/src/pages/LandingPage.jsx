import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  ArrowRight,
  Target,
  BarChart3,
  Layers,
  FileText,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Compass,
  Zap,
  TrendingUp,
} from "lucide-react";

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState("match");

  return (
    <div className="landing-page">
      {/* === Sticky Navigation Header === */}
      <header className="landing-header">
        <nav className="landing-nav">
          <Link to="/" className="landing-logo" aria-label="CareerPilot AI">
            <span className="topnav-logo-mark">
              <Sparkles size={16} />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
            <span className="topnav-logo-badge">AI</span>
          </Link>

          <div className="landing-nav-links">
            <a href="#capabilities">Capabilities</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#demo">Interactive Preview</a>
          </div>

          <div className="landing-nav-actions">
            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign In
            </Link>
            <Link to="/signup" className="btn btn-primary btn-sm">
              <span>Get Started</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </nav>
      </header>

      {/* === Hero Section === */}
      <section className="landing-hero">
        <div className="landing-hero-inner">
          <div className="landing-badge">
            <Sparkles size={14} />
            <span>Intelligent Career Progression Platform</span>
          </div>

          <h1 className="landing-hero-title">
            Stop guessing your job fit.
            <br />
            <span className="landing-hero-highlight">
              Know why you match and how to win.
            </span>
          </h1>

          <p className="landing-hero-subtitle">
            CareerPilot AI analyzes your technical skills, projects, and work history
            against live roles — delivering transparent 5-factor fit breakdowns,
            actionable skill gap insights, and an organized application workspace.
          </p>

          <div className="landing-hero-actions">
            <Link to="/signup" className="btn btn-primary btn-lg">
              <span>Start Free Career Workspace</span>
              <ArrowRight size={18} />
            </Link>
            <a href="#demo" className="btn btn-secondary btn-lg">
              <span>Explore Interactive Demo</span>
            </a>
          </div>

          {/* === Trust / Value Badges (No fake logos/metrics) === */}
          <div className="landing-hero-metrics">
            <div className="metric-pill">
              <CheckCircle2 size={16} className="text-success" />
              <span>Transparent 5-Factor Weighted Algorithm</span>
            </div>
            <div className="metric-pill">
              <Zap size={16} className="text-accent" />
              <span>Real-Time Job Aggregations</span>
            </div>
            <div className="metric-pill">
              <Target size={16} className="text-warning" />
              <span>Automated Skill Gap Identification</span>
            </div>
          </div>
        </div>
      </section>

      {/* === Interactive Product Showcase (Living Demo) === */}
      <section id="demo" className="landing-preview-section">
        <div className="landing-preview-container">
          <div className="landing-preview-header">
            <div className="landing-preview-tabs" role="tablist">
              <button
                className={`preview-tab ${activeTab === "match" ? "active" : ""}`}
                onClick={() => setActiveTab("match")}
                type="button"
                role="tab"
                aria-selected={activeTab === "match"}
              >
                <Target size={16} />
                <span>Match Intelligence</span>
              </button>
              <button
                className={`preview-tab ${activeTab === "skills" ? "active" : ""}`}
                onClick={() => setActiveTab("skills")}
                type="button"
                role="tab"
                aria-selected={activeTab === "skills"}
              >
                <BarChart3 size={16} />
                <span>Skill Gap Coach</span>
              </button>
              <button
                className={`preview-tab ${activeTab === "pipeline" ? "active" : ""}`}
                onClick={() => setActiveTab("pipeline")}
                type="button"
                role="tab"
                aria-selected={activeTab === "pipeline"}
              >
                <Layers size={16} />
                <span>Application Pipeline</span>
              </button>
            </div>
          </div>

          <div className="landing-preview-body">
            {activeTab === "match" && (
              <div className="preview-content-grid">
                <div className="preview-card-main">
                  <div className="preview-job-header">
                    <div>
                      <span className="preview-tag">Target Opportunity</span>
                      <h3 className="preview-job-title">Senior Full-Stack Engineer</h3>
                      <p className="preview-job-company">Stripe • San Francisco, CA (Remote Friendly)</p>
                    </div>
                    <div className="match-score-badge score-high">
                      88% Match
                    </div>
                  </div>

                  <div className="preview-explanation">
                    <p>
                      <strong>Fit Summary:</strong> Exceptional alignment with your backend architecture
                      and Python services. Your completed project <em>Distributed Task Scheduler</em> directly
                      demonstrates the distributed caching and async message queues required for this role.
                    </p>
                  </div>

                  <div className="preview-score-breakdown">
                    <span className="preview-subheading">5-Factor Algorithm Breakdown</span>
                    <div className="preview-bars">
                      <div className="preview-bar-row">
                        <span>Technical Skills (50% weight)</span>
                        <div className="preview-bar-track">
                          <div className="preview-bar-fill" style={{ width: "92%", background: "var(--accent)" }} />
                        </div>
                        <span className="font-mono">92%</span>
                      </div>
                      <div className="preview-bar-row">
                        <span>Projects Alignment (20% weight)</span>
                        <div className="preview-bar-track">
                          <div className="preview-bar-fill" style={{ width: "85%", background: "var(--purple)" }} />
                        </div>
                        <span className="font-mono">85%</span>
                      </div>
                      <div className="preview-bar-row">
                        <span>Experience Match (15% weight)</span>
                        <div className="preview-bar-track">
                          <div className="preview-bar-fill" style={{ width: "80%", background: "var(--info)" }} />
                        </div>
                        <span className="font-mono">80%</span>
                      </div>
                      <div className="preview-bar-row">
                        <span>Role Alignment (10% weight)</span>
                        <div className="preview-bar-track">
                          <div className="preview-bar-fill" style={{ width: "90%", background: "var(--success)" }} />
                        </div>
                        <span className="font-mono">90%</span>
                      </div>
                      <div className="preview-bar-row">
                        <span>Location Fit (5% weight)</span>
                        <div className="preview-bar-track">
                          <div className="preview-bar-fill" style={{ width: "100%", background: "var(--warning)" }} />
                        </div>
                        <span className="font-mono">100%</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="preview-card-sidebar">
                  <div className="preview-skills-group">
                    <h4 className="preview-skills-title text-success">
                      <CheckCircle2 size={16} />
                      <span>Matched Capabilities (8)</span>
                    </h4>
                    <div className="preview-skills-tags">
                      <span className="skill-tag skill-matched">Python</span>
                      <span className="skill-tag skill-matched">React</span>
                      <span className="skill-tag skill-matched">PostgreSQL</span>
                      <span className="skill-tag skill-matched">FastAPI</span>
                      <span className="skill-tag skill-matched">Docker</span>
                      <span className="skill-tag skill-matched">Redis</span>
                      <span className="skill-tag skill-matched">REST APIs</span>
                      <span className="skill-tag skill-matched">Git</span>
                    </div>
                  </div>

                  <div className="preview-skills-group" style={{ marginTop: "var(--space-4)" }}>
                    <h4 className="preview-skills-title text-warning">
                      <AlertCircle size={16} />
                      <span>Skill Growth Focus (2)</span>
                    </h4>
                    <div className="preview-skills-tags">
                      <span className="skill-tag skill-missing">Kafka</span>
                      <span className="skill-tag skill-missing">GraphQL</span>
                    </div>
                    <p className="preview-hint">
                      Adding a small Kafka streaming sample to your profile could boost this fit to 94%.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "skills" && (
              <div className="preview-coach-grid">
                <div className="preview-coach-card">
                  <h4 className="preview-coach-title">
                    <AlertCircle size={18} className="text-warning" />
                    <span>Frequently Missing Across Target Roles</span>
                  </h4>
                  <p className="preview-coach-desc">
                    Based on 14 analyzed software engineering roles matching your profile:
                  </p>
                  <div className="preview-coach-list">
                    <div className="preview-coach-item">
                      <div className="preview-coach-item-header">
                        <strong>AWS / Cloud Deployment</strong>
                        <span className="badge badge-warning">Missing in 65% of roles</span>
                      </div>
                      <p>Recommended: Document your Docker containers or deploy your FastAPI app to AWS ECS.</p>
                    </div>
                    <div className="preview-coach-item">
                      <div className="preview-coach-item-header">
                        <strong>TypeScript</strong>
                        <span className="badge badge-warning">Missing in 50% of roles</span>
                      </div>
                      <p>Recommended: Add TypeScript types to your React component library.</p>
                    </div>
                  </div>
                </div>

                <div className="preview-coach-card">
                  <h4 className="preview-coach-title">
                    <CheckCircle2 size={18} className="text-success" />
                    <span>Top Competitive Strengths</span>
                  </h4>
                  <p className="preview-coach-desc">
                    Your highest-converting competencies in recent matches:
                  </p>
                  <div className="preview-coach-list">
                    <div className="preview-coach-item">
                      <div className="preview-coach-item-header">
                        <strong>Python & Async FastAPI</strong>
                        <span className="badge badge-success">Matched in 100% of roles</span>
                      </div>
                      <p>Strong competitive advantage for high-throughput backend positions.</p>
                    </div>
                    <div className="preview-coach-item">
                      <div className="preview-coach-item-header">
                        <strong>PostgreSQL Database Design</strong>
                        <span className="badge badge-success">Matched in 85% of roles</span>
                      </div>
                      <p>Consistently satisfies senior data-modeling requirements.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "pipeline" && (
              <div className="preview-pipeline-list">
                <div className="preview-pipeline-card">
                  <div className="preview-pipeline-top">
                    <div>
                      <h4 className="preview-pipeline-role">Senior Full-Stack Engineer</h4>
                      <span className="preview-pipeline-company">Stripe</span>
                    </div>
                    <span className="status-badge status-interview">Technical Interview</span>
                  </div>
                  <div className="preview-pipeline-meta">
                    <span>Applied: Oct 12, 2026</span>
                    <span>•</span>
                    <span>Resume: Software_Architect_v3.pdf</span>
                    <span>•</span>
                    <span>Stage: System Design with Lead Architect</span>
                  </div>
                </div>

                <div className="preview-pipeline-card">
                  <div className="preview-pipeline-top">
                    <div>
                      <h4 className="preview-pipeline-role">Backend Infrastructure Engineer</h4>
                      <span className="preview-pipeline-company">Cloudflare</span>
                    </div>
                    <span className="status-badge status-applied">Applied</span>
                  </div>
                  <div className="preview-pipeline-meta">
                    <span>Applied: Oct 14, 2026</span>
                    <span>•</span>
                    <span>Resume: Backend_Distributed_v2.pdf</span>
                    <span>•</span>
                    <span>Stage: Awaiting Recruiter Screen</span>
                  </div>
                </div>

                <div className="preview-pipeline-card">
                  <div className="preview-pipeline-top">
                    <div>
                      <h4 className="preview-pipeline-role">Full-Stack Developer</h4>
                      <span className="preview-pipeline-company">Linear</span>
                    </div>
                    <span className="status-badge status-offer">Offer Received</span>
                  </div>
                  <div className="preview-pipeline-meta">
                    <span>Decision by: Nov 01, 2026</span>
                    <span>•</span>
                    <span>Compensation: Competitive + Equity</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* === Capabilities Section === */}
      <section id="capabilities" className="landing-section">
        <div className="landing-section-header">
          <span className="landing-section-eyebrow">Engineered for Precision</span>
          <h2>Everything you need to navigate your career with confidence</h2>
          <p>
            CareerPilot replaces guesswork with structured data, transparent algorithm scoring,
            and an actionable workspace designed for ambitious job seekers.
          </p>
        </div>

        <div className="landing-capabilities-grid">
          <div className="capability-card">
            <div className="capability-icon">
              <Target size={22} />
            </div>
            <h3>Transparent 5-Factor Matching</h3>
            <p>
              Understand exactly how your background aligns with roles across Skills (50%),
              Projects (20%), Experience (15%), Role Fit (10%), and Location (5%).
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <BarChart3 size={22} />
            </div>
            <h3>Actionable Skill Gap Insights</h3>
            <p>
              Identify missing competencies before applying. Receive contextual recommendations
              on what frameworks or projects will bridge the gap.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <Compass size={22} />
            </div>
            <h3>Opportunity Discovery Hub</h3>
            <p>
              Sync opportunities across modern job boards in real time. Search, filter by
              employment type or experience level, and analyze match scores with one click.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <Layers size={22} />
            </div>
            <h3>Personal Application Pipeline</h3>
            <p>
              Track your journey from saved bookmarks and submitted applications to
              technical rounds and offers — all with contextual notes and resume version tracking.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <FileText size={22} />
            </div>
            <h3>Resume Hub & Master Designation</h3>
            <p>
              Manage multiple tailored PDF resumes. Designate your Master Resume for discovery
              and track which version was submitted for every role.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <TrendingUp size={22} />
            </div>
            <h3>Strategic Career Analytics</h3>
            <p>
              Visualize application funnel conversion rates, frequent skill strengths,
              and interview velocity to refine your job search strategy.
            </p>
          </div>
        </div>
      </section>

      {/* === How It Works Section === */}
      <section id="how-it-works" className="landing-section bg-surface-secondary">
        <div className="landing-section-header">
          <span className="landing-section-eyebrow">The User Journey</span>
          <h2>Four steps to career clarity</h2>
          <p>A systematic progression from profile building to offer negotiation.</p>
        </div>

        <div className="landing-steps-grid">
          <div className="landing-step-card">
            <div className="landing-step-num">01</div>
            <h3>Build Career Profile</h3>
            <p>
              Add your technical skills, completed projects, work history, and upload your
              master PDF resume to create your professional baseline.
            </p>
          </div>

          <div className="landing-step-card">
            <div className="landing-step-num">02</div>
            <h3>Discover & Match</h3>
            <p>
              Browse live opportunities and run multidimensional match calculations to see
              how closely each role fits your target trajectory.
            </p>
          </div>

          <div className="landing-step-card">
            <div className="landing-step-num">03</div>
            <h3>Bridge Skill Gaps</h3>
            <p>
              Review matched strengths and pinpoint critical missing skills to tailor your
              portfolio and resume before submitting.
            </p>
          </div>

          <div className="landing-step-card">
            <div className="landing-step-num">04</div>
            <h3>Track Pipeline to Offer</h3>
            <p>
              Manage applications through every round, update status milestones, and use
              funnel insights to keep momentum high.
            </p>
          </div>
        </div>
      </section>

      {/* === Bottom Call to Action === */}
      <section className="landing-cta-section">
        <div className="landing-cta-card">
          <div className="landing-cta-content">
            <span className="landing-badge">
              <Sparkles size={14} />
              <span>Start Free Today</span>
            </span>
            <h2>Take control of your job search with intelligent precision</h2>
            <p>
              Join students and job seekers using CareerPilot AI to find roles that match
              their strengths and build competitive career profiles.
            </p>
            <div className="landing-cta-buttons">
              <Link to="/signup" className="btn btn-primary btn-lg">
                <span>Create Free Workspace</span>
                <ArrowRight size={18} />
              </Link>
              <Link to="/login" className="btn btn-outline btn-lg">
                <span>Sign In to Existing Account</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* === Footer === */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <div className="landing-logo">
              <span className="topnav-logo-mark">
                <Sparkles size={16} />
              </span>
              <span className="topnav-logo-text">CareerPilot</span>
              <span className="topnav-logo-badge">AI</span>
            </div>
            <p className="landing-footer-desc">
              Intelligent job matching, skill gap coaching, and career workspace.
            </p>
          </div>

          <div className="landing-footer-links">
            <div className="footer-column">
              <h4>Workspace</h4>
              <Link to="/home">Home Command</Link>
              <Link to="/discover">Discover Roles</Link>
              <Link to="/pipeline">Application Pipeline</Link>
              <Link to="/profile">My Career Profile</Link>
            </div>
            <div className="footer-column">
              <h4>Account</h4>
              <Link to="/login">Sign In</Link>
              <Link to="/signup">Register Free</Link>
              <Link to="/forgot-password">Password Reset</Link>
            </div>
          </div>
        </div>

        <div className="landing-footer-bottom">
          <p>&copy; {new Date().getFullYear()} CareerPilot AI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
