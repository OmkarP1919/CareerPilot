import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import JobCard from "../jobs/JobCard";

export default function HomeRecommendedJobs({
  jobs = [],
  savedJobIds = new Set(),
  onToggleSave,
}) {
  const navigate = useNavigate();

  if (!Array.isArray(jobs) || jobs.length === 0) return null;

  // Maximum 2 jobs on mobile, max 3 jobs on desktop
  const displayJobs = jobs.slice(0, 3);

  const handleViewDetails = (job) => {
    if (job?.id) {
      navigate(`/discover/${job.id}`);
    } else {
      navigate("/discover");
    }
  };

  return (
    <section className="home-for-you-section" aria-labelledby="home-for-you-title">
      <div className="home-section-header">
        <div className="home-section-header-text">
          <div className="home-section-tag">
            <Sparkles size={13} aria-hidden="true" />
            <span>Recommended Opportunities</span>
          </div>
          <h2 id="home-for-you-title" className="home-section-heading">
            Opportunities For You
          </h2>
        </div>

        <Link to="/discover" className="btn btn-ghost btn-sm home-see-all-link">
          <span>See all jobs</span>
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>

      <div className="home-jobs-grid">
        {displayJobs.map((job) => (
          <JobCard
            key={job.canonical_key || job.id}
            job={job}
            isSaved={savedJobIds.has(job.id)}
            onToggleSave={onToggleSave}
            onViewDetails={handleViewDetails}
          />
        ))}
      </div>
    </section>
  );
}
