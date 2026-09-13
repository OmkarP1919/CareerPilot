/**
 * Dashboard Utility Module — Phase 7.0B.4
 *
 * Deterministic Next-Action calculation and state inspection.
 * NEVER fabricates completion percentages, match scores, or fake urgency.
 */

/**
 * Determine the user's primary next action based purely on authentic application state.
 *
 * Priority order:
 * 1. Setup Action: No resumes and no profile skills
 * 2. Setup Action: Profile exists but no resume uploaded
 * 3. Urgent Interview: Interview scheduled in the future
 * 4. High-Fit Opportunity: Top matched job with match_score >= 70
 * 5. Pipeline Action: Saved application awaiting submission
 * 6. Default Neutral: Explore jobs
 */
export function determineNextAction({
  resumes = [],
  profile = null,
  applications = [],
  recommendedJobs = [],
  interviews = [],
}) {
  const hasResumes = Array.isArray(resumes) && resumes.length > 0;
  const hasProfileSkills = Boolean(profile?.skills && profile.skills.length > 0);

  // 1. Initial Setup: Completely new user
  if (!hasResumes && !hasProfileSkills) {
    return {
      type: "setup_resume",
      eyebrow: "Recommended Starting Step",
      title: "Upload your resume to activate AI job matching",
      description: "CareerPilot compares your actual skills and experience against live market opportunities.",
      ctaLabel: "Upload Resume",
      ctaLink: "/resumes",
      ctaIcon: "upload",
      secondaryLabel: "Complete Profile",
      secondaryLink: "/profile",
      variant: "accent",
    };
  }

  // 2. Setup: Has profile skills but no resume
  if (!hasResumes) {
    return {
      type: "upload_resume",
      eyebrow: "Activate AI Tailoring",
      title: "Upload a base resume for targeted tailoring",
      description: "You've added skills to your profile. Add a resume file to generate tailored applications and cover letters.",
      ctaLabel: "Upload Resume",
      ctaLink: "/resumes",
      ctaIcon: "upload",
      secondaryLabel: "View Profile",
      secondaryLink: "/profile",
      variant: "accent",
    };
  }

  // 3. Upcoming Interview: Check interviews array
  if (Array.isArray(interviews) && interviews.length > 0) {
    const now = Date.now();
    // Find scheduled interview occurring in the future (or today)
    const upcoming = interviews
      .filter((iv) => {
        if (!iv.scheduled_at) return false;
        const ivTime = new Date(iv.scheduled_at).getTime();
        return ivTime >= now - 2 * 60 * 60 * 1000 && iv.status === "scheduled";
      })
      .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))[0];

    if (upcoming) {
      const formattedDate = new Date(upcoming.scheduled_at).toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });

      return {
        type: "upcoming_interview",
        eyebrow: "Upcoming Interview",
        title: `Prepare for your ${upcoming.kind || "upcoming"} interview`,
        description: `Scheduled for ${formattedDate}. Review notes, required skills, and role details.`,
        ctaLabel: "Open Pipeline",
        ctaLink: "/pipeline",
        ctaIcon: "calendar",
        variant: "purple",
      };
    }
  }

  // 4. High-Fit Recommended Opportunity (authentic score >= 70)
  const bestJob = recommendedJobs?.[0];
  if (bestJob && typeof bestJob.match_score === "number" && bestJob.match_score >= 70) {
    const jobTitle = bestJob.title || "Target Role";
    const company = bestJob.company || "Company";
    const score = bestJob.match_score;

    return {
      type: "tailor_opportunity",
      eyebrow: "Strong Relevant Opportunity",
      title: `Tailor your resume for ${jobTitle}`,
      description: `At ${company} · ${score}% authentic match based on your verified skills and background.`,
      ctaLabel: "Tailor Resume",
      ctaLink: `/discover/${bestJob.id}`,
      ctaState: { openTailor: true },
      ctaIcon: "sparkles",
      secondaryLabel: "View Opportunity",
      secondaryLink: `/discover/${bestJob.id}`,
      variant: "success",
    };
  }

  // 5. Saved Application needing progression
  const savedApp = Array.isArray(applications)
    ? applications.find((a) => (a.status || "").toLowerCase() === "saved")
    : null;

  if (savedApp) {
    const title = savedApp.job_title || "Saved Role";
    const company = savedApp.job_company || "Company";

    return {
      type: "advance_application",
      eyebrow: "Application In Progress",
      title: `Continue your application to ${company}`,
      description: `You have ${title} saved in your pipeline. Ready to apply and advance your status?`,
      ctaLabel: "Open Pipeline",
      ctaLink: "/pipeline",
      ctaIcon: "arrow",
      variant: "neutral",
    };
  }

  // 6. Default Neutral Action
  return {
    type: "explore_jobs",
    eyebrow: "Next Recommended Step",
    title: "Explore relevant career opportunities",
    description: "Browse roles matching your background or run personalized discovery.",
    ctaLabel: "Explore Matching Jobs",
    ctaLink: "/discover",
    ctaIcon: "compass",
    variant: "neutral",
  };
}

/**
 * Summarize application pipeline counts cleanly.
 */
export function derivePipelineSummary(applications) {
  if (!Array.isArray(applications) || applications.length === 0) {
    return null;
  }

  const total = applications.length;
  const active = applications.filter((a) => {
    const s = (a.status || "Saved").toLowerCase();
    return ["preparing", "applied", "assessment", "interview"].includes(s);
  }).length;
  const interviews = applications.filter((a) => (a.status || "").toLowerCase() === "interview").length;
  const offers = applications.filter((a) => (a.status || "").toLowerCase() === "offer").length;

  return { total, active, interviews, offers };
}
