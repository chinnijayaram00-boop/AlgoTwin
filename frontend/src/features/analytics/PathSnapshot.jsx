import { StatusPill } from "../../components/ui/Feedback";

const STATE_LABELS = {
  complete: "Complete",
  current: "In progress",
  upcoming: "Upcoming",
};

/**
 * Where the learner stands in the curriculum: headline progress, one meter
 * per stage, and what is outstanding.
 *
 * Built from the same `build_learning_path` output the `/learning-path`
 * endpoint returns, so this panel and the path page can never disagree about
 * which stage the learner is standing in.
 */
export default function PathSnapshot({ path }) {
  return (
    <div className="path-snapshot">
      <div className="snapshot-headline">
        <strong>{path.completion_percentage}%</strong>
        <span>
          {path.solved_problems} of {path.total_problems} solved · {path.stages_complete}/
          {path.stages_total} stages complete
        </span>
      </div>

      <div className="snapshot-stages">
        {path.stages.map((stage) => (
          <div className="snapshot-stage" data-state={stage.state} key={stage.title}>
            <div className="snapshot-stage-top">
              <strong>
                Stage {stage.index + 1} · {stage.title}
              </strong>
              <span>
                {stage.solved_count}/{stage.problem_count} ·{" "}
                {STATE_LABELS[stage.state] ?? stage.state}
              </span>
            </div>
            <div className="snapshot-meter">
              <span style={{ width: `${stage.completion_percentage}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="snapshot-notes">
        {path.current_stage_title ? (
          <StatusPill tone="violet">Current stage: {path.current_stage_title}</StatusPill>
        ) : (
          <StatusPill tone="success">Path complete</StatusPill>
        )}
        {path.weak_topics.length ? (
          <StatusPill tone="medium">Shore up: {path.weak_topics.join(", ")}</StatusPill>
        ) : (
          <StatusPill tone="success">Nothing to shore up</StatusPill>
        )}
      </div>

      <p className="snapshot-reason">
        {path.recommended_problem ? (
          <>
            Up next: <strong>{path.recommended_problem}</strong> — {path.recommended_reason}
          </>
        ) : (
          <>Every published problem is solved.</>
        )}
      </p>
    </div>
  );
}
