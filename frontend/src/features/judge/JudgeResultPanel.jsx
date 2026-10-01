import { AlertTriangle, CheckCircle2, CircleSlash, Info, Terminal, XCircle } from "lucide-react";

import { StatusPill } from "../../components/ui/Feedback";
import {
  AD_HOC_NOTE,
  RUN_NOTE,
  formatCaseCounts,
  formatPeakMemory,
  formatRunDuration,
  verdictDescription,
  verdictLabel,
  verdictTone,
} from "./judgeStatus";

/**
 * What the last run of the editor's source produced.
 *
 * Presentational, like `ProblemSubmissionPanel`: `WorkspacePage` owns
 * `useCodeRun` so the Run button and this panel read one state, and pressing Run
 * updates both without a second request.
 *
 * The panel is where a run's honesty is made visible, so three things are stated
 * rather than implied:
 *
 * * a run against the problem's cases is a debugging aid, not a submission, and
 *   says so on every state;
 * * a run on the learner's own input has **no verdict**, because nothing was
 *   compared, and the label says exactly that;
 * * a truncated run -- the judge stopped before every case -- is marked as
 *   incomplete, so a partial pass can never read as a full one.
 *
 * Hidden test cases are never shown, and nothing here would render them: the API
 * sends a hidden case's verdict and nothing else.
 */
export default function JudgeResultPanel({ result, running, actionError, onRetry = null }) {
  return (
    <div className="judge-panel">
      {running ? (
        <div className="judge-running" role="status">
          <span className="spinner" />
          <span>Running your code in a separate process…</span>
        </div>
      ) : null}

      {actionError ? (
        <div className="inline-notice" role="alert">
          {actionError}
        </div>
      ) : null}

      {!running && !result ? (
        <div className="judge-idle">
          <Terminal aria-hidden="true" size={15} />
          <p>
            Nothing has been run yet. Run the editor&rsquo;s code against the examples the problem
            publishes.
          </p>
        </div>
      ) : null}

      {result ? (
        <>
          <div className="judge-verdict">
            <StatusPill tone={verdictTone(result.verdict)}>
              {verdictLabel(result.verdict)}
            </StatusPill>
            <span className="judge-verdict-description">{verdictDescription(result.verdict)}</span>
          </div>

          <dl className="judge-facts">
            {result.ad_hoc ? (
              <div>
                <dt>Input</dt>
                <dd>Your own, not graded</dd>
              </div>
            ) : (
              <div>
                <dt>Test cases</dt>
                <dd>{formatCaseCounts(result) ?? "—"}</dd>
              </div>
            )}
            <div>
              <dt>Runtime</dt>
              <dd>{formatRunDuration(result.total_runtime_ms)}</dd>
            </div>
            <div>
              <dt>Peak memory</dt>
              {/*
                Not every platform can measure this -- Windows has no equivalent
                in the standard library the worker uses -- so an absent
                measurement is shown as absent rather than as zero.
              */}
              <dd>{formatPeakMemory(result.peak_memory_mb) ?? "Not measurable here"}</dd>
            </div>
            <div>
              <dt>Limits</dt>
              <dd>
                {result.time_limit_ms} ms · {result.memory_limit_mb} MB
              </dd>
            </div>
          </dl>

          {result.truncated ? (
            <div className="judge-truncated" role="status">
              <AlertTriangle aria-hidden="true" size={15} />
              <span>
                The judge stopped before running every case, so this result is incomplete.
              </span>
            </div>
          ) : null}

          {result.error_message ? (
            <div className="judge-message" role="alert">
              {result.error_message}
            </div>
          ) : null}

          {result.ad_hoc ? <AdHocOutput adHoc={result.ad_hoc} /> : <CaseList cases={result.cases} />}

          {onRetry ? (
            <button className="button button-quiet" onClick={onRetry} type="button">
              Run again
            </button>
          ) : null}
        </>
      ) : null}

      <p className="judge-note">
        <Info aria-hidden="true" size={14} /> {result?.ad_hoc ? AD_HOC_NOTE : RUN_NOTE}
      </p>
    </div>
  );
}

/**
 * The program run against the problem's visible cases.
 *
 * Every case is a visible one -- the run endpoint never executes a hidden case --
 * so the input and the expected answer are shown next to what the program
 * printed. That is the whole value of a debugging run: seeing the two side by
 * side is how the learner works out what to change.
 */
function CaseList({ cases }) {
  if (!Array.isArray(cases) || cases.length === 0) {
    return (
      <div className="judge-idle">
        <CircleSlash aria-hidden="true" size={15} />
        <p>The judge executed no cases, so there is nothing to compare.</p>
      </div>
    );
  }

  return (
    <div className="judge-cases">
      {cases.map((testCase) => {
        const passed = testCase.passed;
        return (
          <div className={`judge-case${passed ? " passed" : " failed"}`} key={testCase.index}>
            <div className="judge-case-heading">
              <span>
                Case {testCase.index + 1} · {formatRunDuration(testCase.duration_ms)}
              </span>
              {passed ? (
                <CheckCircle2 aria-label="Passed" size={15} />
              ) : (
                <XCircle aria-label="Failed" size={15} />
              )}
            </div>
            {testCase.error_message ? (
              <p className="judge-case-error">{testCase.error_message}</p>
            ) : null}
            <div className="judge-case-columns">
              <div>
                <span>Input</span>
                <pre>
                  <code>{testCase.case_input}</code>
                </pre>
              </div>
              <div>
                <span>Expected</span>
                <pre>
                  <code>{testCase.expected_output}</code>
                </pre>
              </div>
              <div>
                <span>Your output</span>
                <pre>
                  <code>{testCase.actual_output}</code>
                </pre>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * The one run of the learner's own input.
 *
 * There is no expected output, so there is no comparison to render: what the
 * program printed, whether it crashed, and how long it took. `stdout` is rendered
 * even when it is empty, because an empty answer is itself the observation.
 */
function AdHocOutput({ adHoc }) {
  return (
    <div className="judge-adhoc">
      <div className="judge-case-heading">
        <span>Your input</span>
      </div>
      <pre>
        <code>{adHoc.stdin}</code>
      </pre>

      <div className="judge-case-heading">
        <span>Your output</span>
        {adHoc.timed_out ? <StatusPill tone="medium">Timed out</StatusPill> : null}
      </div>
      <pre>
        <code>{adHoc.stdout}</code>
      </pre>

      {adHoc.stderr ? (
        <>
          <div className="judge-case-heading">
            <span>Error output</span>
          </div>
          <pre>
            <code>{adHoc.stderr}</code>
          </pre>
        </>
      ) : null}

      <div className="judge-adhoc-exit">
        <span>Exit code</span>
        <strong>{adHoc.exit_code === null ? "—" : adHoc.exit_code}</strong>
      </div>
    </div>
  );
}
