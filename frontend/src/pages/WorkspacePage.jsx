import {
  ArrowLeft,
  Braces,
  CheckCircle2,
  Clock3,
  Gavel,
  Info,
  Play,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import CodeEditor from "../features/problems/CodeEditor";
import JudgeResultPanel from "../features/judge/JudgeResultPanel";
import { formatPeakMemory, formatRunDuration, languageLabel } from "../features/judge/judgeStatus";
import { useCodeRun, useRunnableLanguages } from "../features/judge/useCodeRun";
import ProblemProgressPanel from "../features/progress/ProblemProgressPanel";
import ProblemSubmissionPanel from "../features/submissions/ProblemSubmissionPanel";
import { useProblemSubmissions } from "../features/submissions/useSubmissions";
import { JUDGE_NOTE } from "../features/submissions/submissionStatus";
import { ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { useAuth } from "../features/auth/useAuth";
import { problemApi } from "../services/platformService";

export default function WorkspacePage() {
  const { slug } = useParams();
  const { isAuthenticated } = useAuth();
  const loadProblem = useCallback(() => problemApi.get(slug), [slug]);
  const { data: problem, error, loading, reload } = useApiResource(loadProblem);
  const [language, setLanguage] = useState("javascript");
  const [code, setCode] = useState("");
  // Bumped after every judged submission. The API owns progress, and a
  // submission changes it in two ways: it counts an attempt always, and an
  // accepted verdict also marks the problem solved and records a best runtime.
  // The client cannot tell which happened, so it simply refetches and reads
  // whatever the API now holds.
  const [judgedCount, setJudgedCount] = useState(0);
  // Run against the problem's visible examples by default. Toggled on when the
  // learner wants to try their own input instead, which is a run with no verdict
  // because there is no expected output to compare against.
  const [customInput, setCustomInput] = useState(false);
  const [stdin, setStdin] = useState("");
  // Called before the early returns below so the hook order never changes with
  // the loading state.
  const onJudged = useCallback(() => setJudgedCount((count) => count + 1), []);
  const submissions = useProblemSubmissions(problem?.id, {
    enabled: isAuthenticated && Boolean(problem),
    onJudged,
  });
  const judge = useCodeRun(problem?.id, { enabled: isAuthenticated && Boolean(problem) });
  const { reset: resetRun } = judge;
  // The tab list comes from the registry the judge itself uses, so the editor
  // cannot offer a language the runner will refuse. A failed read falls back to
  // the problem's own list rather than to an invented one.
  const registry = useRunnableLanguages({ enabled: Boolean(problem) });
  const languages = useMemo(() => {
    if (registry.languages.length) return registry.languages;
    return Object.keys(problem?.starter_code || {}).map((id) => ({ id, label: languageLabel(id) }));
  }, [problem?.starter_code, registry.languages]);

  useEffect(() => {
    if (!problem) return;
    const starterCode = problem.starter_code?.[language] || Object.values(problem.starter_code || {})[0] || "";
    setCode(starterCode);
  }, [language, problem]);

  // A problem's tabs are its own: a learner who switches to the binary-search
  // workspace should not keep a language selected that it does not publish.
  useEffect(() => {
    if (languages.length && !languages.some((item) => item.id === language)) {
      setLanguage(languages[0].id);
    }
  }, [language, languages]);

  // A result belongs to the program that produced it. Changing language, or
  // moving to another problem, must not leave the previous run's verdict on
  // screen next to code it did not come from. `resetRun` is the hook's own stable
  // callback rather than the hook's result object, so this fires on a real change
  // and not on every render.
  useEffect(() => {
    resetRun();
  }, [resetRun, language, problem?.id]);

  async function handleSubmit() {
    await submissions.create({ language, sourceCode: code });
  }

  async function handleRun() {
    await judge.run({
      language,
      sourceCode: code,
      stdin: customInput ? stdin : undefined,
    });
  }

  if (loading) return <LoadingState label="Loading problem workspace" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!problem) return null;

  const lastRun = judge.result;

  return (
    <div className="page-stack workspace-page">
      <Link className="back-link" to="/problems"><ArrowLeft size={15} /> Back to problems</Link>
      <PageHeader
        description={problem.summary}
        eyebrow={`${problem.difficulty} · ${problem.topics.join(" · ")}`}
        title={problem.title}
        action={<StatusPill tone="neutral">Visible cases only</StatusPill>}
      />

      <div className="workspace-grid">
        <SectionCard className="editor-card" title="Code workspace" description="Write a solution in the Monaco editor.">
          <div className="editor-toolbar">
            <div className="language-tabs" role="tablist" aria-label="Programming language">
              {languages.map((item) => (
                <button
                  aria-selected={language === item.id}
                  className={`language-tab${language === item.id ? " active" : ""}`}
                  key={item.id}
                  onClick={() => setLanguage(item.id)}
                  role="tab"
                  type="button"
                >
                  <Braces size={14} /> {item.label}
                </button>
              ))}
            </div>
            <button className="button button-quiet" onClick={() => setCode(problem.starter_code?.[language] || "")} type="button">
              <RotateCcw size={14} /> Reset
            </button>
          </div>
          <CodeEditor language={language} onChange={setCode} value={code} />
          <div className="editor-footer">
            <span>
              <Clock3 size={14} /> {problem.time_limit_ms} ms · {problem.memory_limit_mb} MB
            </span>
            <div className="editor-actions">
              {/*
                Run executes the learner's source in a separate worker process
                against the problem's visible examples. It is disabled only when
                there is nothing to run: no session, no source, or a run already
                in flight.
              */}
              <button
                className="button button-quiet"
                disabled={!isAuthenticated || judge.running || !code.trim()}
                onClick={handleRun}
                title={
                  isAuthenticated
                    ? "Run this code against the problem's visible examples."
                    : "Sign in to run your code."
                }
                type="button"
              >
                <Play size={15} /> {judge.running ? "Running…" : "Run test cases"}
              </button>
              <button
                className="button button-primary"
                disabled={submissions.saving || !code.trim()}
                onClick={handleSubmit}
                title="Submit this code to be graded against every test case, hidden ones included."
                type="button"
              >
                <Gavel size={15} /> {submissions.saving ? "Judging…" : "Submit solution"}
              </button>
            </div>
          </div>
          {/*
            Run and Submit sit side by side and do very different things, so the
            difference is stated here rather than left to be discovered: Run grades
            the visible examples and throws the result away, Submit is the graded
            act and is what can mark a problem solved.
          */}
          <div className="inline-notice">
            <Info size={15} /> {JUDGE_NOTE}
          </div>
        </SectionCard>

        <div className="workspace-side-column">
          <SectionCard
            title="Run result"
            description={
              customInput
                ? "One run against your own input. Nothing is compared."
                : "Run against the examples this problem publishes."
            }
          >
            {/*
              Own input is opt-in rather than a second button: two ways to run the
              same code is a choice the learner should make deliberately, and the
              result below has to state which kind of run it was.
            */}
            <div className="judge-mode">
              <button
                aria-pressed={!customInput}
                className={`button button-quiet${!customInput ? " active" : ""}`}
                onClick={() => setCustomInput(false)}
                type="button"
              >
                Visible test cases
              </button>
              <button
                aria-pressed={customInput}
                className={`button button-quiet${customInput ? " active" : ""}`}
                onClick={() => setCustomInput(true)}
                type="button"
              >
                My own input
              </button>
            </div>

            {customInput ? (
              <label className="judge-stdin-label">
                <span>Standard input</span>
                <textarea
                  onChange={(event) => setStdin(event.target.value)}
                  placeholder="Paste one input in the problem's format"
                  rows={4}
                  value={stdin}
                />
              </label>
            ) : null}

            <JudgeResultPanel result={judge.result} running={judge.running} actionError={judge.actionError} />
          </SectionCard>
          <SectionCard title="Your submissions" description="Every submission graded for this problem.">
            <ProblemSubmissionPanel {...submissions} />
          </SectionCard>
          <SectionCard title="Your progress" description="Owned by the judge, stored against your account.">
            <ProblemProgressPanel problemId={problem.id} refreshKey={judgedCount} />
          </SectionCard>
          <SectionCard title="Test cases" description="Examples from the problem contract.">
            <div className="test-case-list">
              {problem.examples?.map((example, index) => (
                <div className="test-case" key={`${example.input}-${index}`}>
                  <div className="test-case-heading"><span>Example {index + 1}</span><CheckCircle2 size={15} /></div>
                  <code>{example.input}</code>
                  <code>{example.output}</code>
                </div>
              ))}
            </div>
          </SectionCard>
          <SectionCard title="Analysis" description="Measured by your last run, nothing inferred.">
            <div className="analysis-list">
              <div><span>Time</span><strong>{formatRunDuration(lastRun?.total_runtime_ms)}</strong></div>
              <div>
                <span>Peak memory</span>
                <strong>{formatPeakMemory(lastRun?.peak_memory_mb) ?? "Not measured"}</strong>
              </div>
              <div><span>Space</span><strong>Not measured</strong></div>
              <div><span>AI explanation</span><strong>Provider pending</strong></div>
            </div>
            {/*
              A run measures time and, where the platform can, memory. It does
              not analyse complexity -- that needs the AI provider boundary, which
              is still a placeholder rather than an integration.
            */}
            <div className="analysis-note"><Sparkles size={15} /> Time and memory come from your last run. Complexity analysis needs the AI provider, which is not connected yet.</div>
          </SectionCard>
        </div>
      </div>

      {problem.constraints ? (
        <SectionCard title="Constraints" description="Keep edge cases visible while you design the solution.">
          <p className="constraints-copy">{problem.constraints}</p>
        </SectionCard>
      ) : null}
    </div>
  );
}
