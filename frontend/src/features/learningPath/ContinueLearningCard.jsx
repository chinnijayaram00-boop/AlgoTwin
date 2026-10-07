import { ArrowRight, Route as RouteIcon } from "lucide-react";
import { Link } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  SectionCard,
  StatusPill,
} from "../../components/ui/Feedback";

function difficultyTone(difficulty) {
  if (difficulty === "Easy") return "easy";
  if (difficulty === "Hard") return "hard";
  return "medium";
}

/**
 * One card, one job: show the single problem the path engine picked and why.
 *
 * It takes the loaded path as a prop instead of fetching it, so the dashboard
 * owns the request (it already owns the progress summary) and this card stays a
 * pure view that can be rendered in isolation by tests.
 */
export default function ContinueLearningCard({ path, loading, error, errorStatus, onRetry }) {
  const recommendation = path?.recommendation ?? null;
  const stageLabel = recommendation ? recommendation.stage_title : path?.current_stage_title;

  return (
    <SectionCard
      description={
        recommendation
          ? recommendation.reason
          : path
            ? "Every stage of the path is finished."
            : "Your next problem, chosen from your own progress."
      }
      title="Continue learning"
    >
      {loading ? <LoadingState label="Loading your learning path" /> : null}

      {errorStatus === 401 && !loading ? (
        <div className="inline-notice" role="alert">
          Sign in again to load your learning path.
        </div>
      ) : null}

      {error && errorStatus !== 401 && !loading ? (
        <ErrorState message={error} onRetry={onRetry} />
      ) : null}

      {!path && !loading && !error ? (
        <EmptyState
          description="The path needs a signed-in session to know where you are."
          title="Sign in to see your path"
        />
      ) : null}

      {recommendation ? (
        <div className="path-next path-next-compact">
          <div className="path-next-copy">
            <div className="path-next-pills">
              <StatusPill tone={difficultyTone(recommendation.problem.difficulty)}>
                {recommendation.problem.difficulty}
              </StatusPill>
              <StatusPill tone="violet">{stageLabel}</StatusPill>
            </div>
            <h4>{recommendation.problem.title}</h4>
          </div>
          <Link className="button button-primary" to={`/problems/${recommendation.problem.slug}`}>
            Start problem <ArrowRight size={16} />
          </Link>
        </div>
      ) : null}

      {path && !recommendation && !loading && !error ? (
        <div className="path-next path-next-compact">
          <div className="path-next-copy">
            <div className="path-next-pills">
              <StatusPill tone="success">
                <RouteIcon size={12} /> Path complete
              </StatusPill>
            </div>
            <h4>Nothing left to recommend</h4>
          </div>
          <Link className="button button-secondary" to="/learning-path">
            View the path <ArrowRight size={16} />
          </Link>
        </div>
      ) : null}
    </SectionCard>
  );
}
