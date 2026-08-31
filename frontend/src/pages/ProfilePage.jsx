import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import Modal from "../components/Modal";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  Briefcase,
  GraduationCap,
  Code2,
  Award,
  Plus,
  Edit3,
  Trash2,
  X,
  Save,
  ExternalLink,
  MapPin,
  Target,
  FolderGit2,
  Sparkles,
  Calendar,
} from "lucide-react";

const SKILL_CATEGORIES = [
  "Programming Languages",
  "Frameworks/Libraries",
  "Databases",
  "Developer Tools",
  "Other Technical Skills",
];

const emptyForm = {
  location: "",
  preferred_roles: "",
  preferred_locations: "",
};

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editMode, setEditMode] = useState(false);
  const [notification, setNotification] = useState(null);

  // Modal states
  const [showEduModal, setShowEduModal] = useState(false);
  const [eduForm, setEduForm] = useState({ degree: "", college: "", branch: "", graduation_year: "", cgpa: "" });
  const [editingEdu, setEditingEdu] = useState(null);

  const [showSkillModal, setShowSkillModal] = useState(false);
  const [skillForm, setSkillForm] = useState({ name: "", category: SKILL_CATEGORIES[0] });

  const [showProjectModal, setShowProjectModal] = useState(false);
  const [projectForm, setProjectForm] = useState({ name: "", description: "", technologies: "", github_url: "", live_url: "" });
  const [editingProject, setEditingProject] = useState(null);

  const [showExpModal, setShowExpModal] = useState(false);
  const [expForm, setExpForm] = useState({ company: "", role: "", start_date: "", end_date: "", description: "", technologies: "" });
  const [editingExp, setEditingExp] = useState(null);

  const [showCertModal, setShowCertModal] = useState(false);
  const [certForm, setCertForm] = useState({ name: "", organization: "", issue_date: "", credential_url: "" });
  const [editingCert, setEditingCert] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchProfile = useCallback(async () => {
    try {
      const data = await api.get("/profile");
      setProfile(data);
      setForm({
        location: data.profile.location || "",
        preferred_roles: data.profile.preferred_roles || "",
        preferred_locations: data.profile.preferred_locations || "",
      });
    } catch {
      notify("Failed to load profile", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const updated = await api.put("/profile", form);
      setProfile((prev) => ({ ...prev, profile: updated }));
      setEditMode(false);
      notify("Career identity updated successfully.");
    } catch {
      notify("Failed to update profile", "error");
    } finally {
      setSaving(false);
    }
  };

  // Education Handlers
  const openAddEdu = () => {
    setEditingEdu(null);
    setEduForm({ degree: "", college: "", branch: "", graduation_year: "", cgpa: "" });
    setShowEduModal(true);
  };
  const openEditEdu = (edu) => {
    setEditingEdu(edu.id);
    setEduForm({
      degree: edu.degree,
      college: edu.college,
      branch: edu.branch || "",
      graduation_year: edu.graduation_year || "",
      cgpa: edu.cgpa || "",
    });
    setShowEduModal(true);
  };
  const handleAddEdu = async () => {
    try {
      const newEdu = await api.post("/profile/education", eduForm);
      setProfile((prev) => ({ ...prev, education: [...prev.education, newEdu] }));
      setShowEduModal(false);
      notify("Education added.");
    } catch {
      notify("Failed to add education", "error");
    }
  };
  const handleUpdateEdu = async (id) => {
    try {
      const updated = await api.put(`/profile/education/${id}`, eduForm);
      setProfile((prev) => ({
        ...prev,
        education: prev.education.map((e) => (e.id === id ? updated : e)),
      }));
      setEditingEdu(null);
      setShowEduModal(false);
      notify("Education updated.");
    } catch {
      notify("Failed to update education", "error");
    }
  };
  const handleDeleteEdu = async (id) => {
    try {
      await api.delete(`/profile/education/${id}`);
      setProfile((prev) => ({
        ...prev,
        education: prev.education.filter((e) => e.id !== id),
      }));
      notify("Education deleted.");
    } catch {
      notify("Failed to delete education", "error");
    }
  };

  // Skill Handlers
  const openAddSkill = () => {
    setSkillForm({ name: "", category: SKILL_CATEGORIES[0] });
    setShowSkillModal(true);
  };
  const handleAddSkill = async () => {
    try {
      const newSkill = await api.post("/profile/skills", skillForm);
      setProfile((prev) => ({ ...prev, skills: [...prev.skills, newSkill] }));
      setShowSkillModal(false);
      notify("Skill added to profile.");
    } catch (err) {
      notify(err.message || "Failed to add skill", "error");
    }
  };
  const handleDeleteSkill = async (id) => {
    try {
      await api.delete(`/profile/skills/${id}`);
      setProfile((prev) => ({
        ...prev,
        skills: prev.skills.filter((s) => s.id !== id),
      }));
      notify("Skill removed.");
    } catch {
      notify("Failed to remove skill", "error");
    }
  };

  // Project Handlers
  const openAddProject = () => {
    setEditingProject(null);
    setProjectForm({ name: "", description: "", technologies: "", github_url: "", live_url: "" });
    setShowProjectModal(true);
  };
  const openEditProject = (proj) => {
    setEditingProject(proj.id);
    setProjectForm({
      name: proj.name,
      description: proj.description || "",
      technologies: proj.technologies || "",
      github_url: proj.github_url || "",
      live_url: proj.live_url || "",
    });
    setShowProjectModal(true);
  };
  const handleAddProject = async () => {
    try {
      const newProj = await api.post("/profile/projects", projectForm);
      setProfile((prev) => ({ ...prev, projects: [...prev.projects, newProj] }));
      setShowProjectModal(false);
      notify("Project added.");
    } catch {
      notify("Failed to add project", "error");
    }
  };
  const handleUpdateProject = async (id) => {
    try {
      const updated = await api.put(`/profile/projects/${id}`, projectForm);
      setProfile((prev) => ({
        ...prev,
        projects: prev.projects.map((p) => (p.id === id ? updated : p)),
      }));
      setEditingProject(null);
      setShowProjectModal(false);
      notify("Project updated.");
    } catch {
      notify("Failed to update project", "error");
    }
  };
  const handleDeleteProject = async (id) => {
    try {
      await api.delete(`/profile/projects/${id}`);
      setProfile((prev) => ({
        ...prev,
        projects: prev.projects.filter((p) => p.id !== id),
      }));
      notify("Project deleted.");
    } catch {
      notify("Failed to delete project", "error");
    }
  };

  // Experience Handlers
  const openAddExp = () => {
    setEditingExp(null);
    setExpForm({ company: "", role: "", start_date: "", end_date: "", description: "", technologies: "" });
    setShowExpModal(true);
  };
  const openEditExp = (exp) => {
    setEditingExp(exp.id);
    setExpForm({
      company: exp.company,
      role: exp.role,
      start_date: exp.start_date || "",
      end_date: exp.end_date || "",
      description: exp.description || "",
      technologies: exp.technologies || "",
    });
    setShowExpModal(true);
  };
  const handleAddExp = async () => {
    try {
      const newExp = await api.post("/profile/experiences", expForm);
      setProfile((prev) => ({ ...prev, experiences: [...prev.experiences, newExp] }));
      setShowExpModal(false);
      notify("Experience added.");
    } catch {
      notify("Failed to add experience", "error");
    }
  };
  const handleUpdateExp = async (id) => {
    try {
      const updated = await api.put(`/profile/experiences/${id}`, expForm);
      setProfile((prev) => ({
        ...prev,
        experiences: prev.experiences.map((e) => (e.id === id ? updated : e)),
      }));
      setEditingExp(null);
      setShowExpModal(false);
      notify("Experience updated.");
    } catch {
      notify("Failed to update experience", "error");
    }
  };
  const handleDeleteExp = async (id) => {
    try {
      await api.delete(`/profile/experiences/${id}`);
      setProfile((prev) => ({
        ...prev,
        experiences: prev.experiences.filter((e) => e.id !== id),
      }));
      notify("Experience deleted.");
    } catch {
      notify("Failed to delete experience", "error");
    }
  };

  // Certification Handlers
  const openAddCert = () => {
    setEditingCert(null);
    setCertForm({ name: "", organization: "", issue_date: "", credential_url: "" });
    setShowCertModal(true);
  };
  const openEditCert = (cert) => {
    setEditingCert(cert.id);
    setCertForm({
      name: cert.name,
      organization: cert.organization || "",
      issue_date: cert.issue_date || "",
      credential_url: cert.credential_url || "",
    });
    setShowCertModal(true);
  };
  const handleAddCert = async () => {
    try {
      const newCert = await api.post("/profile/certifications", certForm);
      setProfile((prev) => ({ ...prev, certifications: [...prev.certifications, newCert] }));
      setShowCertModal(false);
      notify("Certification added.");
    } catch {
      notify("Failed to add certification", "error");
    }
  };
  const handleUpdateCert = async (id) => {
    try {
      const updated = await api.put(`/profile/certifications/${id}`, certForm);
      setProfile((prev) => ({
        ...prev,
        certifications: prev.certifications.map((c) => (c.id === id ? updated : c)),
      }));
      setEditingCert(null);
      setShowCertModal(false);
      notify("Certification updated.");
    } catch {
      notify("Failed to update certification", "error");
    }
  };
  const handleDeleteCert = async (id) => {
    try {
      await api.delete(`/profile/certifications/${id}`);
      setProfile((prev) => ({
        ...prev,
        certifications: prev.certifications.filter((c) => c.id !== id),
      }));
      notify("Certification deleted.");
    } catch {
      notify("Failed to delete certification", "error");
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 260, height: 32 }} />
        </div>
        <div className="grid-2">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  // Calculate profile completeness
  const hasSkills = profile?.skills?.length > 0;
  const hasEdu = profile?.education?.length > 0;
  const hasProjects = profile?.projects?.length > 0;
  const hasExp = profile?.experiences?.length > 0;
  const hasPreferences = !!(profile?.profile?.preferred_roles || profile?.profile?.location);

  const completedCount = [hasSkills, hasEdu, hasProjects, hasExp, hasPreferences].filter(Boolean).length;
  const completenessPct = Math.round((completedCount / 5) * 100);

  return (
    <div className="page">
      {/* === Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>My Career Profile</h1>
            <p>Your comprehensive professional baseline for precision job matching</p>
          </div>
          <div className="page-header-actions">
            <div className="profile-completeness-badge">
              <Sparkles size={14} className="text-accent" />
              <span>Profile Strength: <strong>{completenessPct}%</strong></span>
            </div>
          </div>
        </div>
      </header>

      {notification && (
        <div className={`alert alert-${notification.type}`} role="alert">
          {notification.msg}
        </div>
      )}

      {/* === Target Trajectory & Preferences Card === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Target size={18} className="text-accent" />
            <span>Target Trajectory & Preferences</span>
          </h2>
          {!editMode && (
            <button className="btn btn-outline btn-sm" onClick={() => setEditMode(true)}>
              <Edit3 size={14} />
              <span>Edit Preferences</span>
            </button>
          )}
        </div>

        <div className="card-body">
          {editMode ? (
            <div className="profile-edit-form">
              <div className="form-group">
                <label className="form-label">Current Location</label>
                <input
                  className="form-input"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="e.g. San Francisco, CA (or Remote)"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Target Job Roles</label>
                <input
                  className="form-input"
                  value={form.preferred_roles}
                  onChange={(e) => setForm({ ...form, preferred_roles: e.target.value })}
                  placeholder="e.g. Senior Frontend Engineer, Full-Stack Developer"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Preferred Work Locations / Remote</label>
                <input
                  className="form-input"
                  value={form.preferred_locations}
                  onChange={(e) => setForm({ ...form, preferred_locations: e.target.value })}
                  placeholder="e.g. Remote, New York, Seattle"
                />
              </div>
              <div className="form-actions" style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                <button className="btn btn-primary btn-sm" onClick={handleSaveProfile} disabled={saving}>
                  <Save size={14} />
                  <span>{saving ? "Saving..." : "Save Identity"}</span>
                </button>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => {
                    setEditMode(false);
                    fetchProfile();
                  }}
                >
                  <X size={14} />
                  <span>Cancel</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="profile-pref-grid">
              <div className="profile-pref-item">
                <div className="pref-label">
                  <MapPin size={14} />
                  <span>Current Base</span>
                </div>
                <div className="pref-value">{profile?.profile?.location || "Not specified"}</div>
              </div>
              <div className="profile-pref-item">
                <div className="pref-label">
                  <Target size={14} />
                  <span>Target Roles</span>
                </div>
                <div className="pref-value">{profile?.profile?.preferred_roles || "Not specified"}</div>
              </div>
              <div className="profile-pref-item">
                <div className="pref-label">
                  <Briefcase size={14} />
                  <span>Preferred Locations</span>
                </div>
                <div className="pref-value">{profile?.profile?.preferred_locations || "Remote Friendly"}</div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* === Technical Capabilities & Skills === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Code2 size={18} className="text-accent" />
            <span>Technical Capabilities & Skills ({profile?.skills?.length || 0})</span>
          </h2>
          <button className="btn btn-primary btn-sm" onClick={openAddSkill}>
            <Plus size={14} />
            <span>Add Skill</span>
          </button>
        </div>

        <div className="card-body">
          {profile?.skills?.length === 0 ? (
            <EmptyState
              icon={Code2}
              title="No technical skills added yet"
              text="Skills represent 50% of your job fit score. Add programming languages, frameworks, and tools."
              action={
                <button className="btn btn-primary btn-sm" onClick={openAddSkill}>
                  <Plus size={14} /> Add First Skill
                </button>
              }
            />
          ) : (
            <div className="profile-skills-categories">
              {SKILL_CATEGORIES.map((cat) => {
                const catSkills = profile.skills.filter((s) => s.category === cat);
                if (catSkills.length === 0) return null;
                return (
                  <div key={cat} className="profile-skill-category-group">
                    <h4 className="profile-skill-category-title">{cat}</h4>
                    <div className="profile-skill-tags-wrap">
                      {catSkills.map((s) => (
                        <span key={s.id} className="profile-interactive-skill-tag">
                          <span>{s.skill_name}</span>
                          <button
                            className="skill-remove-btn"
                            onClick={() => handleDeleteSkill(s.id)}
                            aria-label={`Remove ${s.skill_name}`}
                            type="button"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* === Projects Section === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <FolderGit2 size={18} className="text-accent" />
            <span>Featured Projects ({profile?.projects?.length || 0})</span>
          </h2>
          <button className="btn btn-outline btn-sm" onClick={openAddProject}>
            <Plus size={14} />
            <span>Add Project</span>
          </button>
        </div>

        <div className="card-body">
          {profile?.projects?.length === 0 ? (
            <EmptyState
              icon={FolderGit2}
              title="No featured projects added"
              text="Projects demonstrate hands-on experience and represent 20% of your match calculation."
              action={
                <button className="btn btn-secondary btn-sm" onClick={openAddProject}>
                  <Plus size={14} /> Add Project
                </button>
              }
            />
          ) : (
            <div className="profile-entities-list">
              {profile.projects.map((proj) => (
                <div key={proj.id} className="profile-entity-card">
                  <div className="entity-card-content">
                    <div className="entity-title-row">
                      <h3 className="entity-name">{proj.name}</h3>
                      <div className="entity-actions">
                        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEditProject(proj)} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button className="btn btn-ghost btn-icon btn-sm btn-danger" onClick={() => handleDeleteProject(proj.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {proj.description && <p className="entity-description">{proj.description}</p>}

                    {proj.technologies && (
                      <div className="entity-tech-row">
                        <span className="entity-tech-label">Tech Stack:</span>
                        <span className="entity-tech-tags">{proj.technologies}</span>
                      </div>
                    )}

                    <div className="entity-links-row">
                      {proj.github_url && (
                        <a href={proj.github_url} target="_blank" rel="noopener noreferrer" className="entity-link">
                          <ExternalLink size={13} />
                          <span>GitHub Repository</span>
                        </a>
                      )}
                      {proj.live_url && (
                        <a href={proj.live_url} target="_blank" rel="noopener noreferrer" className="entity-link">
                          <ExternalLink size={13} />
                          <span>Live Demonstration</span>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Work Experience === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Briefcase size={18} className="text-accent" />
            <span>Work Experience ({profile?.experiences?.length || 0})</span>
          </h2>
          <button className="btn btn-outline btn-sm" onClick={openAddExp}>
            <Plus size={14} />
            <span>Add Experience</span>
          </button>
        </div>

        <div className="card-body">
          {profile?.experiences?.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No work history recorded"
              text="Add past roles, internships, or freelance work (15% match weighting)."
              action={
                <button className="btn btn-secondary btn-sm" onClick={openAddExp}>
                  <Plus size={14} /> Add Work History
                </button>
              }
            />
          ) : (
            <div className="profile-timeline-list">
              {profile.experiences.map((exp) => (
                <div key={exp.id} className="profile-timeline-item">
                  <div className="timeline-marker" />
                  <div className="timeline-content">
                    <div className="entity-title-row">
                      <div>
                        <h3 className="entity-name">{exp.role}</h3>
                        <span className="entity-subtitle">{exp.company}</span>
                      </div>
                      <div className="entity-actions">
                        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEditExp(exp)} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button className="btn btn-ghost btn-icon btn-sm btn-danger" onClick={() => handleDeleteExp(exp.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="timeline-date-chip">
                      <Calendar size={13} />
                      <span>{exp.start_date} — {exp.end_date || "Present"}</span>
                    </div>

                    {exp.description && <p className="entity-description">{exp.description}</p>}
                    {exp.technologies && (
                      <div className="entity-tech-row">
                        <span className="entity-tech-label">Applied Technologies:</span>
                        <span className="entity-tech-tags">{exp.technologies}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Education & Academic History === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <GraduationCap size={18} className="text-accent" />
            <span>Education History ({profile?.education?.length || 0})</span>
          </h2>
          <button className="btn btn-outline btn-sm" onClick={openAddEdu}>
            <Plus size={14} />
            <span>Add Education</span>
          </button>
        </div>

        <div className="card-body">
          {profile?.education?.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="No educational history added"
              text="Add your university degree, major, and graduation year."
              action={
                <button className="btn btn-secondary btn-sm" onClick={openAddEdu}>
                  <Plus size={14} /> Add Degree
                </button>
              }
            />
          ) : (
            <div className="profile-entities-list">
              {profile.education.map((edu) => (
                <div key={edu.id} className="profile-entity-card">
                  <div className="entity-card-content">
                    <div className="entity-title-row">
                      <div>
                        <h3 className="entity-name">{edu.degree}{edu.branch ? ` in ${edu.branch}` : ""}</h3>
                        <span className="entity-subtitle">{edu.college}</span>
                      </div>
                      <div className="entity-actions">
                        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEditEdu(edu)} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button className="btn btn-ghost btn-icon btn-sm btn-danger" onClick={() => handleDeleteEdu(edu.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="entity-meta-row">
                      {edu.graduation_year && <span>Class of {edu.graduation_year}</span>}
                      {edu.cgpa && <span>• CGPA / Grade: {edu.cgpa}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Certifications === */}
      <section className="card">
        <div className="card-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Award size={18} className="text-accent" />
            <span>Certifications & Credentials ({profile?.certifications?.length || 0})</span>
          </h2>
          <button className="btn btn-outline btn-sm" onClick={openAddCert}>
            <Plus size={14} />
            <span>Add Certification</span>
          </button>
        </div>

        <div className="card-body">
          {profile?.certifications?.length === 0 ? (
            <EmptyState
              icon={Award}
              title="No certifications added yet"
              text="Add verified certificates from AWS, Google Cloud, Coursera, or industry providers."
              action={
                <button className="btn btn-secondary btn-sm" onClick={openAddCert}>
                  <Plus size={14} /> Add Certification
                </button>
              }
            />
          ) : (
            <div className="profile-entities-list">
              {profile.certifications.map((cert) => (
                <div key={cert.id} className="profile-entity-card">
                  <div className="entity-card-content">
                    <div className="entity-title-row">
                      <div>
                        <h3 className="entity-name">{cert.name}</h3>
                        <span className="entity-subtitle">{cert.organization}</span>
                      </div>
                      <div className="entity-actions">
                        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEditCert(cert)} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button className="btn btn-ghost btn-icon btn-sm btn-danger" onClick={() => handleDeleteCert(cert.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="entity-meta-row">
                      {cert.issue_date && <span>Issued: {cert.issue_date}</span>}
                      {cert.credential_url && (
                        <a href={cert.credential_url} target="_blank" rel="noopener noreferrer" className="entity-link" style={{ marginLeft: 8 }}>
                          <ExternalLink size={13} />
                          <span>View Verified Credential</span>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Modals === */}
      {/* Skill Modal */}
      <Modal
        isOpen={showSkillModal}
        onClose={() => setShowSkillModal(false)}
        title="Add Technical Skill"
        footer={
          <div className="form-actions" style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleAddSkill}>
              <Save size={14} /> Add Skill
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowSkillModal(false)}>
              Cancel
            </button>
          </div>
        }
      >
        <div className="form-group">
          <label className="form-label">Skill Name *</label>
          <input
            className="form-input"
            value={skillForm.name}
            onChange={(e) => setSkillForm({ ...skillForm, name: e.target.value })}
            placeholder="e.g. Python, React, PostgreSQL, Docker"
            required
          />
        </div>
        <div className="form-group">
          <label className="form-label">Category</label>
          <select
            className="form-select"
            value={skillForm.category}
            onChange={(e) => setSkillForm({ ...skillForm, category: e.target.value })}
          >
            {SKILL_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </Modal>

      {/* Project Modal */}
      <Modal
        isOpen={showProjectModal}
        onClose={() => setShowProjectModal(false)}
        title={editingProject ? "Edit Featured Project" : "Add Featured Project"}
        footer={
          <div className="form-actions" style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={editingProject ? () => handleUpdateProject(editingProject) : handleAddProject}
            >
              <Save size={14} /> {editingProject ? "Save Changes" : "Add Project"}
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowProjectModal(false)}>
              Cancel
            </button>
          </div>
        }
      >
        <div className="form-group">
          <label className="form-label">Project Name *</label>
          <input
            className="form-input"
            value={projectForm.name}
            onChange={(e) => setProjectForm({ ...projectForm, name: e.target.value })}
            placeholder="e.g. Distributed Task Queue"
            required
          />
        </div>
        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea
            className="form-textarea"
            rows={3}
            value={projectForm.description}
            onChange={(e) => setProjectForm({ ...projectForm, description: e.target.value })}
            placeholder="Describe the problem solved, architectural choices, and impact..."
          />
        </div>
        <div className="form-group">
          <label className="form-label">Technologies Used</label>
          <input
            className="form-input"
            value={projectForm.technologies}
            onChange={(e) => setProjectForm({ ...projectForm, technologies: e.target.value })}
            placeholder="e.g. Python, Redis, FastAPI, Docker"
          />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">GitHub URL</label>
            <input
              className="form-input"
              type="url"
              value={projectForm.github_url}
              onChange={(e) => setProjectForm({ ...projectForm, github_url: e.target.value })}
              placeholder="https://github.com/..."
            />
          </div>
          <div className="form-group">
            <label className="form-label">Live Demo URL</label>
            <input
              className="form-input"
              type="url"
              value={projectForm.live_url}
              onChange={(e) => setProjectForm({ ...projectForm, live_url: e.target.value })}
              placeholder="https://..."
            />
          </div>
        </div>
      </Modal>

      {/* Experience Modal */}
      <Modal
        isOpen={showExpModal}
        onClose={() => setShowExpModal(false)}
        title={editingExp ? "Edit Experience" : "Add Work Experience"}
        footer={
          <div className="form-actions" style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={editingExp ? () => handleUpdateExp(editingExp) : handleAddExp}
            >
              <Save size={14} /> {editingExp ? "Save Changes" : "Add Experience"}
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowExpModal(false)}>
              Cancel
            </button>
          </div>
        }
      >
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Company *</label>
            <input
              className="form-input"
              value={expForm.company}
              onChange={(e) => setExpForm({ ...expForm, company: e.target.value })}
              placeholder="e.g. Stripe"
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Role Title *</label>
            <input
              className="form-input"
              value={expForm.role}
              onChange={(e) => setExpForm({ ...expForm, role: e.target.value })}
              placeholder="e.g. Backend Engineer Intern"
              required
            />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Start Date</label>
            <input
              className="form-input"
              value={expForm.start_date}
              onChange={(e) => setExpForm({ ...expForm, start_date: e.target.value })}
              placeholder="e.g. Jun 2024"
            />
          </div>
          <div className="form-group">
            <label className="form-label">End Date</label>
            <input
              className="form-input"
              value={expForm.end_date}
              onChange={(e) => setExpForm({ ...expForm, end_date: e.target.value })}
              placeholder="e.g. Aug 2024 (or Present)"
            />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Description / Achievements</label>
          <textarea
            className="form-textarea"
            rows={3}
            value={expForm.description}
            onChange={(e) => setExpForm({ ...expForm, description: e.target.value })}
            placeholder="Key responsibilities and engineering accomplishments..."
          />
        </div>
        <div className="form-group">
          <label className="form-label">Technologies</label>
          <input
            className="form-input"
            value={expForm.technologies}
            onChange={(e) => setExpForm({ ...expForm, technologies: e.target.value })}
            placeholder="e.g. Go, Kubernetes, PostgreSQL"
          />
        </div>
      </Modal>

      {/* Education Modal */}
      <Modal
        isOpen={showEduModal}
        onClose={() => setShowEduModal(false)}
        title={editingEdu ? "Edit Education" : "Add Education"}
        footer={
          <div className="form-actions" style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={editingEdu ? () => handleUpdateEdu(editingEdu) : handleAddEdu}
            >
              <Save size={14} /> {editingEdu ? "Save Changes" : "Add Education"}
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowEduModal(false)}>
              Cancel
            </button>
          </div>
        }
      >
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Degree *</label>
            <input
              className="form-input"
              value={eduForm.degree}
              onChange={(e) => setEduForm({ ...eduForm, degree: e.target.value })}
              placeholder="e.g. B.Tech, B.S."
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Major / Branch</label>
            <input
              className="form-input"
              value={eduForm.branch}
              onChange={(e) => setEduForm({ ...eduForm, branch: e.target.value })}
              placeholder="e.g. Computer Science"
            />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">University / College *</label>
          <input
            className="form-input"
            value={eduForm.college}
            onChange={(e) => setEduForm({ ...eduForm, college: e.target.value })}
            placeholder="e.g. University of California, Berkeley"
            required
          />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Graduation Year</label>
            <input
              className="form-input"
              value={eduForm.graduation_year}
              onChange={(e) => setEduForm({ ...eduForm, graduation_year: e.target.value })}
              placeholder="e.g. 2026"
            />
          </div>
          <div className="form-group">
            <label className="form-label">CGPA / GPA</label>
            <input
              className="form-input"
              value={eduForm.cgpa}
              onChange={(e) => setEduForm({ ...eduForm, cgpa: e.target.value })}
              placeholder="e.g. 3.8 / 4.0"
            />
          </div>
        </div>
      </Modal>

      {/* Certification Modal */}
      <Modal
        isOpen={showCertModal}
        onClose={() => setShowCertModal(false)}
        title={editingCert ? "Edit Certification" : "Add Certification"}
        footer={
          <div className="form-actions" style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={editingCert ? () => handleUpdateCert(editingCert) : handleAddCert}
            >
              <Save size={14} /> {editingCert ? "Save Changes" : "Add Certification"}
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowCertModal(false)}>
              Cancel
            </button>
          </div>
        }
      >
        <div className="form-group">
          <label className="form-label">Certification Name *</label>
          <input
            className="form-input"
            value={certForm.name}
            onChange={(e) => setCertForm({ ...certForm, name: e.target.value })}
            placeholder="e.g. AWS Certified Solutions Architect"
            required
          />
        </div>
        <div className="form-group">
          <label className="form-label">Issuing Organization</label>
          <input
            className="form-input"
            value={certForm.organization}
            onChange={(e) => setCertForm({ ...certForm, organization: e.target.value })}
            placeholder="e.g. Amazon Web Services, Google Cloud"
          />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Issue Date</label>
            <input
              className="form-input"
              value={certForm.issue_date}
              onChange={(e) => setCertForm({ ...certForm, issue_date: e.target.value })}
              placeholder="e.g. Jan 2025"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Credential Verification URL</label>
            <input
              className="form-input"
              type="url"
              value={certForm.credential_url}
              onChange={(e) => setCertForm({ ...certForm, credential_url: e.target.value })}
              placeholder="https://..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
