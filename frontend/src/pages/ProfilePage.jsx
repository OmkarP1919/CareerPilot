import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../services/api";
import { SkeletonCard } from "../components/Skeleton";
import ProfileRecordModal from "../components/profile/ProfileRecordModal";
import ProfileResumeSyncModal from "../components/profile/ProfileResumeSyncModal";
import SkillAutocomplete from "../components/profile/SkillAutocomplete";
import {
  buildResumeProfileDiff,
  applyResumeProfileSync,
} from "../components/profile/profileAutofillUtils";
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
  Calendar,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

export default function ProfilePage() {
  const { currentUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [savingGoals, setSavingGoals] = useState(false);
  const [notification, setNotification] = useState(null);

  // Resume Sync states
  const [parsedResumeData, setParsedResumeData] = useState(null);
  const [syncDiff, setSyncDiff] = useState(null);
  const [showSyncModal, setShowSyncModal] = useState(false);

  // Career Goals inline editing
  const [editingGoals, setEditingGoals] = useState(false);
  const [goalsForm, setGoalsForm] = useState({
    location: "",
    preferred_roles: "",
    preferred_locations: "",
  });

  // Skills quick-add input
  const [addingSkill, setAddingSkill] = useState(false);

  // Generic record modal state (experience, project, education, certification)
  const [recordModalConfig, setRecordModalConfig] = useState({
    isOpen: false,
    type: null,
    initialData: null,
  });

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  // Fetch full profile and resume data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, resumeList] = await Promise.all([
        api.get("/profile"),
        api.get("/resumes").catch(() => []),
      ]);

      if (profileData) {
        setProfile(profileData);
        setGoalsForm({
          location: profileData.profile?.location || "",
          preferred_roles: profileData.profile?.preferred_roles || "",
          preferred_locations: profileData.profile?.preferred_locations || "",
        });
      }

      const safeResumes = Array.isArray(resumeList) ? resumeList : [];

      // Check if user has a master or parsed resume
      const masterResume = safeResumes.find((r) => r.is_master) || safeResumes[0];
      if (masterResume?.id) {
        const parsedRes = await api.get(`/resumes/${masterResume.id}/parsed`).catch(() => null);
        if (parsedRes?.data && Object.keys(parsedRes.data).length > 0) {
          setParsedResumeData({
            id: masterResume.id,
            name: masterResume.original_filename || "Master Resume",
            data: parsedRes.data,
          });
          const diff = buildResumeProfileDiff(parsedRes.data, profileData);
          setSyncDiff(diff);
        }
      }
    } catch (err) {
      setError(err?.message || "Failed to load profile data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Save Career Goals
  const handleSaveGoals = async (e) => {
    if (e) e.preventDefault();
    setSavingGoals(true);
    try {
      const updated = await api.put("/profile", goalsForm);
      setProfile((prev) => ({ ...prev, profile: updated }));
      setEditingGoals(false);
      notify("Career goals updated.");
    } catch {
      notify("Failed to update career goals", "error");
    } finally {
      setSavingGoals(false);
    }
  };

  // Quick-add Skill
  const handleAddSkill = async (skillNameStr) => {
    const skillName = skillNameStr.trim();
    if (!skillName) return;

    // Client deduplication
    const existing = (profile?.skills || []).some(
      (s) => (s.skill_name || "").toLowerCase() === skillName.toLowerCase()
    );
    if (existing) {
      notify(`"${skillName}" is already in your profile`, "error");
      return;
    }

    setAddingSkill(true);
    try {
      const created = await api.post("/profile/skills", {
        name: skillName,
        category: "Other Technical Skills",
      });
      setProfile((prev) => ({ ...prev, skills: [...(prev.skills || []), created] }));
      notify(`Added ${skillName}`);
    } catch (err) {
      notify(err.message || "Failed to add skill", "error");
    } finally {
      setAddingSkill(false);
    }
  };

  const handleDeleteSkill = async (id) => {
    try {
      await api.delete(`/profile/skills/${id}`);
      setProfile((prev) => ({
        ...prev,
        skills: (prev.skills || []).filter((s) => s.id !== id),
      }));
      notify("Skill removed.");
    } catch {
      notify("Failed to remove skill", "error");
    }
  };

  // Resume Sync Confirmation Action
  const handleConfirmResumeSync = async () => {
    if (!syncDiff || !parsedResumeData?.data) return;
    const result = await applyResumeProfileSync(syncDiff, api, profile);
    if (result.count > 0) {
      notify(`Successfully added ${result.count} items from ${parsedResumeData.name}!`);
      await fetchData();
    } else if (result.errors.length > 0) {
      notify(`Sync encountered errors: ${result.errors[0]}`, "error");
    }
  };

  // Generic Record Add / Edit handler
  const handleSaveRecord = async (formData) => {
    const { type, initialData } = recordModalConfig;
    const isEdit = Boolean(initialData?.id);
    const id = initialData?.id;

    try {
      if (type === "experience") {
        if (isEdit) {
          const updated = await api.put(`/profile/experiences/${id}`, formData);
          setProfile((prev) => ({
            ...prev,
            experiences: prev.experiences.map((e) => (e.id === id ? updated : e)),
          }));
          notify("Experience updated.");
        } else {
          const created = await api.post("/profile/experiences", formData);
          setProfile((prev) => ({
            ...prev,
            experiences: [...(prev.experiences || []), created],
          }));
          notify("Experience added.");
        }
      } else if (type === "project") {
        if (isEdit) {
          const updated = await api.put(`/profile/projects/${id}`, formData);
          setProfile((prev) => ({
            ...prev,
            projects: prev.projects.map((p) => (p.id === id ? updated : p)),
          }));
          notify("Project updated.");
        } else {
          const created = await api.post("/profile/projects", formData);
          setProfile((prev) => ({
            ...prev,
            projects: [...(prev.projects || []), created],
          }));
          notify("Project added.");
        }
      } else if (type === "education") {
        if (isEdit) {
          const updated = await api.put(`/profile/education/${id}`, formData);
          setProfile((prev) => ({
            ...prev,
            education: prev.education.map((e) => (e.id === id ? updated : e)),
          }));
          notify("Education updated.");
        } else {
          const created = await api.post("/profile/education", formData);
          setProfile((prev) => ({
            ...prev,
            education: [...(prev.education || []), created],
          }));
          notify("Education record added.");
        }
      } else if (type === "certification") {
        if (isEdit) {
          const updated = await api.put(`/profile/certifications/${id}`, formData);
          setProfile((prev) => ({
            ...prev,
            certifications: prev.certifications.map((c) => (c.id === id ? updated : c)),
          }));
          notify("Certification updated.");
        } else {
          const created = await api.post("/profile/certifications", formData);
          setProfile((prev) => ({
            ...prev,
            certifications: [...(prev.certifications || []), created],
          }));
          notify("Certification added.");
        }
      }
    } catch {
      notify(`Failed to save ${type}`, "error");
    }
  };

  const handleDeleteRecord = async (type, id) => {
    try {
      if (type === "experience") {
        await api.delete(`/profile/experiences/${id}`);
        setProfile((prev) => ({
          ...prev,
          experiences: prev.experiences.filter((e) => e.id !== id),
        }));
        notify("Experience deleted.");
      } else if (type === "project") {
        await api.delete(`/profile/projects/${id}`);
        setProfile((prev) => ({
          ...prev,
          projects: prev.projects.filter((p) => p.id !== id),
        }));
        notify("Project deleted.");
      } else if (type === "education") {
        await api.delete(`/profile/education/${id}`);
        setProfile((prev) => ({
          ...prev,
          education: prev.education.filter((e) => e.id !== id),
        }));
        notify("Education deleted.");
      } else if (type === "certification") {
        await api.delete(`/profile/certifications/${id}`);
        setProfile((prev) => ({
          ...prev,
          certifications: prev.certifications.filter((c) => c.id !== id),
        }));
        notify("Certification deleted.");
      }
    } catch {
      notify(`Failed to delete ${type}`, "error");
    }
  };

  const openAddRecord = (type) => {
    setRecordModalConfig({ isOpen: true, type, initialData: null });
  };

  const openEditRecord = (type, item) => {
    setRecordModalConfig({ isOpen: true, type, initialData: item });
  };

  const closeRecordModal = () => {
    setRecordModalConfig({ isOpen: false, type: null, initialData: null });
  };

  if (loading) {
    return (
      <div className="page profile-page-unified" aria-busy="true">
        <header className="page-header">
          <div className="skeleton" style={{ width: "240px", height: "32px" }} />
          <div className="skeleton" style={{ width: "160px", height: "18px", marginTop: "8px" }} />
        </header>
        <div className="stack" style={{ gap: "var(--space-6)" }}>
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page profile-page-unified">
        <div className="empty-state" style={{ padding: "4rem 2rem", textAlign: "center" }}>
          <AlertCircle size={48} className="text-danger" style={{ marginBottom: "var(--space-4)", margin: "0 auto var(--space-4)" }} />
          <h3>Failed to load profile</h3>
          <p className="text-secondary">{error}</p>
          <button className="btn btn-primary" style={{ marginTop: "var(--space-4)" }} onClick={fetchData}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "Career Profile";
  const userLocation = profile?.profile?.location;
  const targetRoles = profile?.profile?.preferred_roles;
  const preferredLocations = profile?.profile?.preferred_locations;

  return (
    <div className="page profile-page-unified">
      {/* === 1. Profile Header === */}
      <header className="page-header profile-clean-header">
        <div className="profile-header-main">
          <div className="profile-avatar-circle">
            {currentUser?.photoURL ? (
              <img src={currentUser.photoURL} alt={displayName} className="profile-avatar-img" />
            ) : (
              <span>{displayName.slice(0, 2).toUpperCase()}</span>
            )}
          </div>
          <div className="profile-header-text">
            <h1 className="profile-title">{displayName}</h1>
            <p className="profile-subtitle">
              {targetRoles || "Career Profile"}
              {userLocation && ` · ${userLocation}`}
            </p>
          </div>
        </div>

        {/* 2. Prominent Sync from Resume Action */}
        {parsedResumeData && (
          <div className="profile-header-sync-action">
            <button
              type="button"
              className="btn btn-outline btn-sm profile-sync-btn"
              onClick={() => setShowSyncModal(true)}
              title="Sync skills and experience from your parsed resume"
            >
              <RefreshCw size={15} aria-hidden="true" />
              <span>Update from Resume</span>
              {syncDiff?.hasChanges && (
                <span className="badge badge-accent badge-sm" style={{ marginLeft: "4px" }}>
                  {syncDiff.totalItems} new
                </span>
              )}
            </button>
          </div>
        )}
      </header>

      {notification && (
        <div className={`alert alert-${notification.type}`} role="alert">
          {notification.msg}
        </div>
      )}

      {/* === 3. Target Career Goals Card === */}
      <section className="card profile-card" aria-labelledby="profile-goals-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <Target size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-goals-heading" className="profile-section-title">
              Target Career Goals
            </h2>
          </div>
          {!editingGoals && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setEditingGoals(true)}
            >
              <Edit3 size={14} aria-hidden="true" />
              <span>Edit Goals</span>
            </button>
          )}
        </div>

        <div className="card-body">
          {editingGoals ? (
            <form onSubmit={handleSaveGoals} className="profile-edit-form">
              <div className="form-group">
                <label className="form-label" htmlFor="goal-location">Current Base Location</label>
                <input
                  id="goal-location"
                  className="form-input"
                  value={goalsForm.location}
                  onChange={(e) => setGoalsForm({ ...goalsForm, location: e.target.value })}
                  placeholder="e.g. San Francisco, CA or Remote"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="goal-roles">Target Job Roles</label>
                <input
                  id="goal-roles"
                  className="form-input"
                  value={goalsForm.preferred_roles}
                  onChange={(e) => setGoalsForm({ ...goalsForm, preferred_roles: e.target.value })}
                  placeholder="e.g. Senior Frontend Engineer, Full-Stack Developer"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="goal-locations">Preferred Work Locations / Remote</label>
                <input
                  id="goal-locations"
                  className="form-input"
                  value={goalsForm.preferred_locations}
                  onChange={(e) => setGoalsForm({ ...goalsForm, preferred_locations: e.target.value })}
                  placeholder="e.g. Remote, New York, Seattle"
                />
              </div>
              <div className="form-actions" style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={savingGoals}>
                  <Save size={14} aria-hidden="true" />
                  <span>{savingGoals ? "Saving..." : "Save Goals"}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setEditingGoals(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div className="profile-goals-preview-grid">
              <div className="goals-preview-item">
                <span className="goals-label">
                  <MapPin size={14} aria-hidden="true" /> Current Base
                </span>
                <span className="goals-value">{userLocation || "Not specified"}</span>
              </div>
              <div className="goals-preview-item">
                <span className="goals-label">
                  <Target size={14} aria-hidden="true" /> Target Roles
                </span>
                <span className="goals-value">{targetRoles || "Not specified"}</span>
              </div>
              <div className="goals-preview-item">
                <span className="goals-label">
                  <Briefcase size={14} aria-hidden="true" /> Preferred Locations
                </span>
                <span className="goals-value">{preferredLocations || "Remote / Any"}</span>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* === 4. Technical Skills === */}
      <section className="card profile-card" aria-labelledby="profile-skills-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <Code2 size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-skills-heading" className="profile-section-title">
              Technical Skills ({profile?.skills?.length || 0})
            </h2>
          </div>
        </div>

        <div className="card-body">
          {/* Fast Quick-Add Field with Autocomplete */}
          <div className="profile-quick-skill-wrapper">
            <SkillAutocomplete
              onAddSkill={handleAddSkill}
              disabled={addingSkill}
              profileSkills={profile?.skills || []}
            />
          </div>

          {/* Interactive Tag Cloud */}
          <div className="profile-skills-cloud" style={{ marginTop: "var(--space-4)" }}>
            {(!profile?.skills || profile.skills.length === 0) ? (
              <p className="text-sm text-secondary">
                No skills added yet. Type your key languages and tools above, or sync from your parsed resume.
              </p>
            ) : (
              profile.skills.map((s) => (
                <span key={s.id} className="profile-skill-chip">
                  <span>{s.skill_name}</span>
                  <button
                    type="button"
                    className="skill-chip-remove"
                    onClick={() => handleDeleteSkill(s.id)}
                    aria-label={`Remove ${s.skill_name}`}
                  >
                    <X size={12} aria-hidden="true" />
                  </button>
                </span>
              ))
            )}
          </div>
        </div>
      </section>

      {/* === 5. Work Experience === */}
      <section className="card profile-card" aria-labelledby="profile-exp-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <Briefcase size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-exp-heading" className="profile-section-title">
              Work Experience ({profile?.experiences?.length || 0})
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => openAddRecord("experience")}
          >
            <Plus size={14} aria-hidden="true" />
            <span>Add Experience</span>
          </button>
        </div>

        <div className="card-body">
          {(!profile?.experiences || profile.experiences.length === 0) ? (
            <p className="text-sm text-secondary">No work experience entries recorded yet.</p>
          ) : (
            <div className="profile-entities-list">
              {profile.experiences.map((exp) => (
                <div key={exp.id} className="profile-entity-item">
                  <div className="entity-item-top">
                    <div>
                      <h3 className="entity-item-title">{exp.role}</h3>
                      <span className="entity-item-subtitle">{exp.company}</span>
                    </div>
                    <div className="entity-item-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => openEditRecord("experience", exp)}
                        title="Edit Experience"
                        aria-label={`Edit ${exp.role} at ${exp.company}`}
                      >
                        <Edit3 size={15} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm btn-danger"
                        onClick={() => handleDeleteRecord("experience", exp.id)}
                        title="Delete Experience"
                        aria-label={`Delete ${exp.role} at ${exp.company}`}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  {(exp.start_date || exp.end_date) && (
                    <div className="entity-date-row">
                      <Calendar size={13} aria-hidden="true" />
                      <span>{exp.start_date || "Start"} — {exp.end_date || "Present"}</span>
                    </div>
                  )}

                  {exp.description && (
                    <p className="entity-item-desc">{exp.description}</p>
                  )}

                  {exp.technologies && (
                    <div className="entity-tech-line">
                      <span className="text-muted text-xs">Technologies:</span>
                      <span className="text-xs font-medium">{exp.technologies}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === 6. Featured Projects === */}
      <section className="card profile-card" aria-labelledby="profile-proj-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <FolderGit2 size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-proj-heading" className="profile-section-title">
              Featured Projects ({profile?.projects?.length || 0})
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => openAddRecord("project")}
          >
            <Plus size={14} aria-hidden="true" />
            <span>Add Project</span>
          </button>
        </div>

        <div className="card-body">
          {(!profile?.projects || profile.projects.length === 0) ? (
            <p className="text-sm text-secondary">No featured projects added yet.</p>
          ) : (
            <div className="profile-entities-list">
              {profile.projects.map((proj) => (
                <div key={proj.id} className="profile-entity-item">
                  <div className="entity-item-top">
                    <h3 className="entity-item-title">{proj.name}</h3>
                    <div className="entity-item-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => openEditRecord("project", proj)}
                        title="Edit Project"
                        aria-label={`Edit ${proj.name}`}
                      >
                        <Edit3 size={15} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm btn-danger"
                        onClick={() => handleDeleteRecord("project", proj.id)}
                        title="Delete Project"
                        aria-label={`Delete ${proj.name}`}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  {proj.description && (
                    <p className="entity-item-desc">{proj.description}</p>
                  )}

                  {proj.technologies && (
                    <div className="entity-tech-line">
                      <span className="text-muted text-xs">Stack:</span>
                      <span className="text-xs font-medium">{proj.technologies}</span>
                    </div>
                  )}

                  {(proj.github_url || proj.live_url) && (
                    <div className="entity-links-row">
                      {proj.github_url && (
                        <a
                          href={proj.github_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="entity-link"
                        >
                          <ExternalLink size={13} aria-hidden="true" />
                          <span>GitHub Repository</span>
                        </a>
                      )}
                      {proj.live_url && (
                        <a
                          href={proj.live_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="entity-link"
                        >
                          <ExternalLink size={13} aria-hidden="true" />
                          <span>Live Demo</span>
                        </a>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === 7. Education History === */}
      <section className="card profile-card" aria-labelledby="profile-edu-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <GraduationCap size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-edu-heading" className="profile-section-title">
              Education ({profile?.education?.length || 0})
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => openAddRecord("education")}
          >
            <Plus size={14} aria-hidden="true" />
            <span>Add Education</span>
          </button>
        </div>

        <div className="card-body">
          {(!profile?.education || profile.education.length === 0) ? (
            <p className="text-sm text-secondary">No educational history recorded.</p>
          ) : (
            <div className="profile-entities-list">
              {profile.education.map((edu) => (
                <div key={edu.id} className="profile-entity-item">
                  <div className="entity-item-top">
                    <div>
                      <h3 className="entity-item-title">
                        {edu.degree}
                        {edu.branch && ` in ${edu.branch}`}
                      </h3>
                      <span className="entity-item-subtitle">{edu.college}</span>
                    </div>
                    <div className="entity-item-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => openEditRecord("education", edu)}
                        title="Edit Education"
                        aria-label={`Edit ${edu.degree}`}
                      >
                        <Edit3 size={15} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm btn-danger"
                        onClick={() => handleDeleteRecord("education", edu.id)}
                        title="Delete Education"
                        aria-label={`Delete ${edu.degree}`}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  {(edu.graduation_year || edu.cgpa) && (
                    <div className="entity-meta-row">
                      {edu.graduation_year && <span>Class of {edu.graduation_year}</span>}
                      {edu.cgpa && <span> · Grade / GPA: {edu.cgpa}</span>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === 8. Certifications === */}
      <section className="card profile-card" aria-labelledby="profile-cert-heading">
        <div className="card-header profile-card-header">
          <div className="profile-section-title-wrap">
            <Award size={18} className="text-accent" aria-hidden="true" />
            <h2 id="profile-cert-heading" className="profile-section-title">
              Certifications ({profile?.certifications?.length || 0})
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => openAddRecord("certification")}
          >
            <Plus size={14} aria-hidden="true" />
            <span>Add Certification</span>
          </button>
        </div>

        <div className="card-body">
          {(!profile?.certifications || profile.certifications.length === 0) ? (
            <p className="text-sm text-secondary">No certifications recorded.</p>
          ) : (
            <div className="profile-entities-list">
              {profile.certifications.map((cert) => (
                <div key={cert.id} className="profile-entity-item">
                  <div className="entity-item-top">
                    <div>
                      <h3 className="entity-item-title">{cert.name}</h3>
                      {cert.organization && (
                        <span className="entity-item-subtitle">{cert.organization}</span>
                      )}
                    </div>
                    <div className="entity-item-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => openEditRecord("certification", cert)}
                        title="Edit Certification"
                        aria-label={`Edit ${cert.name}`}
                      >
                        <Edit3 size={15} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm btn-danger"
                        onClick={() => handleDeleteRecord("certification", cert.id)}
                        title="Delete Certification"
                        aria-label={`Delete ${cert.name}`}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  {(cert.issue_date || cert.credential_url) && (
                    <div className="entity-meta-row">
                      {cert.issue_date && <span>Issued: {cert.issue_date}</span>}
                      {cert.credential_url && (
                        <a
                          href={cert.credential_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="entity-link"
                          style={{ marginLeft: "8px" }}
                        >
                          <ExternalLink size={13} aria-hidden="true" />
                          <span>View Credential</span>
                        </a>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* === Modals === */}
      {/* 1. Resume Sync Confirmation Dialog */}
      <ProfileResumeSyncModal
        isOpen={showSyncModal}
        onClose={() => setShowSyncModal(false)}
        diff={syncDiff}
        resumeName={parsedResumeData?.name}
        onConfirmSync={handleConfirmResumeSync}
      />

      {/* 2. Generic Record Add/Edit Dialog */}
      <ProfileRecordModal
        isOpen={recordModalConfig.isOpen}
        onClose={closeRecordModal}
        type={recordModalConfig.type}
        initialData={recordModalConfig.initialData}
        onSave={handleSaveRecord}
      />
    </div>
  );
}
