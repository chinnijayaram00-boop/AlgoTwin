import { ArrowUpRight, Clock3, Layers3 } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusPill } from "../../components/ui/Feedback";
import ProgressStatusPill from "../progress/ProgressStatusPill";
import { formatTimestamp } from "../progress/progressStatus";

function difficultyTone(difficulty) {
  if (difficulty === "Easy") return "easy";
  if (difficulty === "Hard") return "hard";
  return "medium";
}

export default function ProblemCard({ problem }) {
  // The learner endpoint supplies the status alongside every problem, so a card
  // needs no extra request. A problem from a non-progress caller (or one that
  // failed to load) simply has no status, and the card stays as it was.
  const hasStatus = typeof problem.status === "string";

  return (
    <Link className="problem-card" to={`/problems/${problem.slug}`}>
      <div className="problem-card-topline">
        <StatusPill tone={difficultyTone(problem.difficulty)}>{problem.difficulty}</StatusPill>
        {hasStatus ? <ProgressStatusPill showIcon status={problem.status} /> : <ArrowUpRight size={17} />}
      </div>
      <h3>{problem.title}</h3>
      <p>{problem.summary}</p>
      <div className="problem-card-meta">
        <span>
          <Layers3 size={14} />
          {problem.topics.slice(0, 2).join(" · ")}
        </span>
        <span>
          <Clock3 size={14} />
          {hasStatus && problem.solved_at ? `Solved ${formatTimestamp(problem.solved_at)}` : "Practice"}
        </span>
      </div>
    </Link>
  );
}
