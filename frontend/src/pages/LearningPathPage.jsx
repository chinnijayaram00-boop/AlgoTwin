import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Circle,
  Compass,
  Layers3,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  SectionCard,
  StatusPill,
} from "../components/ui/Feedback";
import { useLearningPath } from "../features/learningPath/useLearningPath";
import ProblemCard from "../features/problems/ProblemCard";

const stageStateMeta = {
  complete: { label: "Complete", tone: "success", icon: CheckCircle2 },
  current: { label: "In progress", tone: "violet", icon: Compass },
  upcoming: { label: "Upcoming", tone: "neutral", icon: Circle },
};

function difficultyTone(difficulty) {
  if (difficulty === "Easy") return "easy";
  if (difficulty === "Hard") return "hard";
  return "medium";
}

export default function LearningPathPage() {
  const { data, error, errorStatus, loading, reload } = useLearningPath();

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Learning path"
        title="Follow the stages in order."
        description="Stages follow the catalog curriculum. Inside a stage the next problem is chosen from your own progress, never at random."
        action={
          <Link className="button button-primary" to="/problems">
            Open problem library <ArrowRight size={16} />
          </Link>
        }
      />

      {loading ? <LoadingState label="Building your learning path" /> : null}
      {errorStatus === 401 ? (
        <div className="inline-notice" role="alert">
          Sign in again to load your learning path. Your session may have expired.
        </div>
      ) : null}
      {error && errorStatus !== 401 ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? <LearningPathView path={data} /> : null}
    </div>
  );
}

function LearningPathView({ path }) {
  const current =
    path.current_stage_index === null || path.current_stage_index === undefined
      ? null
      : path.stages[path.current_stage_index] || null;
  const recommendation = path.recommendation;

  return (
    <>
      <div className="metrics-grid">
        <MetricCard
          detail={`${path.solved_problems} of ${path.total_problems} solved`}
          icon={Layers3}
          label="Overall progress"
          value={`${path.completion_percentage}%`}
        />
        <MetricCard
          detail={
            current ? `Stage ${current.index + 1} of ${path.stages_total}` : "Every stage finished"
          }
          icon={Compass}
          label="Current stage"
          value={current ? current.title : "Complete"}
        />
        <MetricCard
          detail="Stages fully solved"
          icon={CheckCircle2}
          label="Stages complete"
          value={`${path.stages_complete}/${path.stages_total}`}
        />
        <MetricCard
          detail="Started, not solved"
          icon={Target}
          label="Topics to shore up"
          value={path.weak_topics.length}
        />
      </div>

      <SectionCard
        description={recommendation ? recommendation.reason : "Every published problem is solved."}
        title="Your next problem"
      >
        {recommendation ? (
          <NextProblemCard recommendation={recommendation} />
        ) : (
          <EmptyState
            action={
              <Link className="button button-secondary" to="/problems?status=solved">
                Review solved problems <ArrowRight size={16} />
              </Link>
            }
            description="You have worked through every stage of the path."
            title="Path complete"
          />
        )}
      </SectionCard>

      {current ? (
        <SectionCard
          description={`${current.solved_count} of ${current.problem_count} solved in this stage.`}
          title={`Stage ${current.index + 1} · ${current.title}`}
        >
          <div className="problem-grid">
            {current.problems.map((problem) => (
              <ProblemCard key={problem.problem_id} problem={problem} />
            ))}
          </div>
        </SectionCard>
      ) : null}

      <SectionCard
        description="Ordered by the curriculum, with your completion state on each stage."
        title="Path stages"
      >
        <div className="stage-list">
          {path.stages.map((stage) => (
            <StageRow key={stage.key} stage={stage} />
          ))}
        </div>
      </SectionCard>

      <SectionCard
        description="Primary topics you have opened but not finished."
        title="Topics to shore up"
      >
        {path.weak_topics.length > 0 ? (
          <div className="path-topic-list">
            {path.weak_topics.map((topic) => (
              <StatusPill key={topic} tone="medium">
                {topic}
              </StatusPill>
            ))}
          </div>
        ) : (
          <EmptyState
            description="No topic has been left half-finished."
            title="Nothing to shore up"
          />
        )}
      </SectionCard>
    </>
  );
}

function NextProblemCard({ recommendation }) {
  const problem = recommendation.problem;
  return (
    <div className="path-next">
      <div className="path-next-copy">
        <div className="path-next-pills">
          <StatusPill tone={difficultyTone(problem.difficulty)}>{problem.difficulty}</StatusPill>
          <StatusPill tone="violet">{recommendation.stage_title}</StatusPill>
        </div>
        <h4>{problem.title}</h4>
        <p>{problem.summary}</p>
      </div>
      <Link className="button button-primary" to={`/problems/${problem.slug}`}>
        Start problem <ArrowRight size={16} />
      </Link>
    </div>
  );
}

function StageRow({ stage }) {
  const meta = stageStateMeta[stage.state] || stageStateMeta.upcoming;
  const Icon = meta.icon;
  const needsPrerequisite = stage.prerequisite_ready === false && stage.prerequisite_title;

  return (
    <div className="stage-row" data-state={stage.state}>
      <span className="stage-number">{String(stage.index + 1).padStart(2, "0")}</span>
      <div className="stage-icon">
        <Icon size={17} />
      </div>
      <div>
        <strong>{stage.title}</strong>
        <p>
          {stage.solved_count}/{stage.problem_count} solved · {meta.label}
          {needsPrerequisite ? ` · needs ${stage.prerequisite_title} first` : ""}
        </p>
      </div>
      <ChevronRight aria-hidden="true" size={16} />
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail }) {
  return (
    <div className="metric-card">
      <div className="metric-icon">
        <Icon size={18} />
      </div>
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}
