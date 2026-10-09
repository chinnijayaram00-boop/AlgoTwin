import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, StatusPill } from "../../components/ui/Feedback";
import { difficultyTone } from "./personalizationFormat";

/**
 * The next few problems to try, all inside the learner's current stage.
 *
 * The first entry is the learning path's own recommendation, reason and all; the
 * rest are the other unsolved problems in the same stage. Following the list
 * never pulls the learner out of the stage they are standing in.
 */
export default function RecommendationList({ recommendations }) {
  if (!recommendations || recommendations.length === 0) {
    return (
      <EmptyState
        description="Solve or attempt a problem and the coach will line up what to do next."
        title="Nothing to recommend yet"
      />
    );
  }

  return (
    <ol className="coach-recommendations">
      {recommendations.map((recommendation, index) => (
        <li className="coach-recommendation" key={recommendation.problem_id}>
          <div className="coach-recommendation-copy">
            <div className="coach-recommendation-pills">
              <StatusPill tone={difficultyTone(recommendation.difficulty)}>
                {recommendation.difficulty}
              </StatusPill>
              {index === 0 ? <StatusPill tone="violet">Recommended next</StatusPill> : null}
            </div>
            <strong>{recommendation.title}</strong>
            <p>{recommendation.reason}</p>
          </div>
          <Link
            className={`button ${index === 0 ? "button-primary" : "button-quiet"}`}
            to={`/problems/${recommendation.slug}`}
          >
            Open <ArrowRight size={14} />
          </Link>
        </li>
      ))}
    </ol>
  );
}
