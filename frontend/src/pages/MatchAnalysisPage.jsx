import { useParams, Navigate } from "react-router-dom";

/**
 * MatchAnalysisPage (Consolidation Target)
 *
 * In Phase 7.0B.1, all Match Analysis capability has been consolidated directly
 * into the primary Job Details experience (/discover/:id?tab=fit) so users never
 * have to leave the job context to evaluate fit.
 *
 * This component remains strictly backward-compatible to preserve old bookmarks,
 * links, and internal route transitions without broken links.
 */
export default function MatchAnalysisPage() {
  const params = useParams();
  const effectiveJobId = params.id || params.jobId;

  if (!effectiveJobId) {
    return <Navigate to="/discover" replace />;
  }

  return <Navigate to={`/discover/${effectiveJobId}?tab=fit`} replace />;
}
