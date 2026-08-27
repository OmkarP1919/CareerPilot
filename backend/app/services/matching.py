from sqlalchemy.orm import Session
from app.models.profile import Profile, UserSkill, Project, Experience
from app.models.job import Job


def normalize(text: str) -> str:
    return text.lower().strip()


def parse_skills(skills_text: str) -> set[str]:
    if not skills_text:
        return set()
    return {normalize(s.strip()) for s in skills_text.split(",") if s.strip()}


def calculate_match(
    user_id: str,
    job: Job,
    db: Session,
    profile: Profile | None = None,
    user_skills_set: set[str] | None = None,
    user_projects: list[Project] | None = None,
    user_experiences: list[Experience] | None = None,
) -> dict:
    if profile is None:
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return _empty_result()

    if user_skills_set is None:
        user_skills_set = {
            normalize(us.skill.name)
            for us in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
        }
    if user_projects is None:
        user_projects = db.query(Project).filter(Project.profile_id == profile.id).all()
    if user_experiences is None:
        user_experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()

    user_skills = user_skills_set

    required_skills = parse_skills(job.required_skills)
    job_desc_words = set()
    if job.description:
        for word in job.description.lower().split():
            cleaned = "".join(c for c in word if c.isalnum())
            if len(cleaned) > 2:
                job_desc_words.add(cleaned)

    if required_skills:
        all_job_skills = required_skills
        matched_skills = sorted(list(all_job_skills & user_skills))
        missing_skills = sorted(list(all_job_skills - user_skills))
        matched_count = len(matched_skills)
        skills_score = (matched_count / len(required_skills)) * 100
    else:
        # If no required_skills specified on external job, infer from description words
        all_job_skills = {s for s in user_skills if s in job_desc_words}
        matched_skills = sorted(list(all_job_skills))
        missing_skills = []
        skills_score = 70.0 if matched_skills else (50.0 if user_skills else 0.0)

    relevant_projects = []
    for proj in user_projects:
        proj_tech = {normalize(t.strip()) for t in (proj.technologies or "").split(",") if t.strip()}
        proj_text = f"{proj.name} {proj.description or ''}".lower()
        proj_words = {normalize(w) for w in proj_text.split()}
        overlap = proj_tech & all_job_skills
        keyword_match = bool(proj_words & job_desc_words)
        if overlap or keyword_match:
            relevant_projects.append(proj.name)
    project_score = min(100, (len(relevant_projects) / max(1, min(3, len(user_projects)))) * 100) if user_projects else 0

    relevant_experience = []
    for exp in user_experiences:
        exp_tech = {normalize(t.strip()) for t in (exp.technologies or "").split(",") if t.strip()}
        exp_text = f"{exp.role} {exp.company} {exp.description or ''}".lower()
        exp_words = {normalize(w) for w in exp_text.split()}
        overlap = exp_tech & all_job_skills
        keyword_match = bool(exp_words & job_desc_words)
        if overlap or keyword_match:
            relevant_experience.append(f"{exp.role} at {exp.company}")
    experience_score = min(100, (len(relevant_experience) / max(1, min(2, len(user_experiences)))) * 100) if user_experiences else 0

    role_score = 0
    if profile.preferred_roles:
        preferred = {normalize(r.strip()) for r in profile.preferred_roles.split(",") if r.strip()}
        title_words = {normalize(w) for w in job.title.split()}
        if preferred & title_words:
            role_score = 100
        elif any(p in normalize(job.title) for p in preferred):
            role_score = 80
        else:
            role_score = 30
    else:
        role_score = 50

    location_score = 0
    if profile.preferred_locations and job.location:
        preferred_locs = {normalize(l.strip()) for l in profile.preferred_locations.split(",") if l.strip()}
        job_loc = normalize(job.location)
        if any(loc in job_loc for loc in preferred_locs):
            location_score = 100
        elif "remote" in job_loc:
            location_score = 80
        else:
            location_score = 20
    else:
        location_score = 50

    overall_score = round(
        skills_score * 0.50
        + project_score * 0.20
        + experience_score * 0.15
        + role_score * 0.10
        + location_score * 0.05
    )

    explanation = _build_explanation(
        overall_score, skills_score, matched_skills, missing_skills,
        relevant_projects, relevant_experience, role_score, location_score, job,
    )

    return {
        "overall_score": overall_score,
        "skills_score": round(skills_score),
        "project_score": round(project_score),
        "experience_score": round(experience_score),
        "role_score": round(role_score),
        "location_score": round(location_score),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "relevant_projects": relevant_projects,
        "relevant_experience": relevant_experience,
        "explanation": explanation,
    }


def _build_explanation(
    overall, skills, matched, missing, projects, experience, role, location, job,
):
    parts = []
    parts.append(f"Overall match: {overall}%")

    if matched:
        parts.append(f"Technical skills match: {skills}% — you have {len(matched)} of the required skills ({', '.join(matched[:5])}{'...' if len(matched) > 5 else ''}).")
    else:
        parts.append("No matching technical skills found.")

    if missing:
        parts.append(f"Missing skills: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}. Consider learning these to improve your match.")

    if projects:
        parts.append(f"Relevant projects found: {len(projects)} ({', '.join(projects[:3])}).")
    else:
        parts.append("No directly relevant projects found.")

    if experience:
        parts.append(f"Relevant experience: {', '.join(experience[:2])}.")
    else:
        parts.append("No directly relevant work experience found.")

    if role >= 80:
        parts.append("This job aligns well with your preferred roles.")
    elif role < 50:
        parts.append("This job may not fully align with your preferred roles.")

    if location >= 80:
        parts.append("This job location matches your preferences.")
    elif location < 30:
        parts.append("This job location does not match your preferences.")

    return " ".join(parts)


def _empty_result():
    return {
        "overall_score": 0,
        "skills_score": 0,
        "project_score": 0,
        "experience_score": 0,
        "role_score": 0,
        "location_score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "relevant_projects": [],
        "relevant_experience": [],
        "explanation": "No profile found. Complete your profile to get match scores.",
    }
