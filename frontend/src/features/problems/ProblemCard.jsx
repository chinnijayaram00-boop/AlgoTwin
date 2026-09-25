import { ArrowUpRight, Clock3, Layers3 } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusPill } from "../../components/ui/Feedback";

function difficultyTone(difficulty) {
  if (difficulty === "Easy") return "easy";
  if (difficulty === "Hard") return "hard";
  return "medium";
}

export default function ProblemCard({ problem }) {
  return (
    <Link className="problem-card" to={`/problems/${problem.slug}`}>
      <div className="problem-card-topline">
        <StatusPill tone={difficultyTone(problem.difficulty)}>{problem.difficulty}</StatusPill>
        <ArrowUpRight size={17} />
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
          Practice
        </span>
      </div>
    </Link>
  );
}
