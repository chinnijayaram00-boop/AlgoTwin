import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Gavel,
  Mic2,
  Play,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, useRef } from "react";

import { ErrorState, EmptyState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { problemApi } from "../services/platformService";
import { useApiResource } from "../hooks/useApiResource";
import CodeEditor from "../features/problems/CodeEditor";
import DiagnosisPanel from "../features/ai/DiagnosisPanel";
import {
  formatRemainingSeconds,
  interviewStatusLabel,
  interviewStatusTone,
} from "../features/interviews/interviewStatus";
import {
  useInterviewCountdown,
  useInterviewHistory,
  useInterviewReport,
  useInterviews,
} from "../features/interviews/useInterviews";
import {
  formatCaseCounts,
  formatRuntime,
  formatSubmittedAt,
  languageLabel,
  statusLabel,
  statusTone,
} from "../features/submissions/submissionStatus";

const DEFAULT_ROLE = "Software Engineer";
const DEFAULT_QUESTION_COUNT = 3;
const DEFAULT_DURATION_MINUTES = 30;
const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 10;
const MIN_DURATION_MINUTES = 5;
const MAX_DURATION_MINUTES = 120;
const DIFFICULTIES = ["Easy", "Medium", "Hard"];
//: The countdown turns amber below five minutes, like a real clock.
const WARN_BELOW_SECONDS = 300;

export default function InterviewsPage() {
  const interviews = useInterviews();
  const [reportId, setReportId] = useState(null);

  // The history is shown only when no session is open; an abandoned session
  // returns the learner to the setup view, which then shows the abandoned row.
  const isSetup = !interviews.session || interviews.session.status === "abandoned";
  const history = useInterviewHistory({
    enabled: isSetup,
    refreshKey: interviews.session?.id ?? 0,
  });

  const sessionCompleted = interviews.session?.status === "completed";
  const reportInterviewId = reportId ?? (sessionCompleted ? interviews.session.id : null);
  const report = useInterviewReport(reportInterviewId, { enabled: reportInterviewId != null });

  // A stable identity for the callbacks below: the hook's own reload is a
  // memoized load of the active session, while the hook's object is fresh on
  // every render.
  const reloadInterview = interviews.reload;

  const handleStartAnother = useCallback(async () => {
    setReportId(null);
    await reloadInterview();
  }, [reloadInterview]);

  const handleCloseReport = useCallback(() => setReportId(null), []);
  const handleOpenReport = useCallback((interviewId) => setReportId(interviewId), []);

  // The countdown reaching zero is not the end of the session -- it is the
  // moment to let the server finalise it. Only the API's stored `expires_at`
  // can complete a session, so we ask it again and take whatever state it
  // returns (usually a completed, timed-out session).
  const handleExpire = useCallback(() => {
    setReportId(null);
    reloadInterview();
  }, [reloadInterview]);

  if (interviews.loading) {
    return (
      <div className="page-stack">
        <InterviewPageHeader />
        <LoadingState label="Finding your interview session" />
      </div>
    );
  }

  if (interviews.loadError) {
    return (
      <div className="page-stack">
        <InterviewPageHeader />
        <ErrorState message={interviews.loadError} onRetry={interviews.reload} />
      </div>
    );
  }

  if (reportInterviewId != null) {
    return (
      <ReportView
        error={report.error}
        errorStatus={report.errorStatus}
        fromHistory={reportId != null}
        loading={report.loading}
        onClose={handleCloseReport}
        onRetry={report.reload}
        onStartAnother={handleStartAnother}
        report={report.data}
      />
    );
  }

  const { session } = interviews;

  if (isSetup) {
    return (
      <SetupView
        actionError={interviews.actionError}
        history={history}
        onOpenReport={handleOpenReport}
        onCreate={interviews.create}
        saving={interviews.saving}
      />
    );
  }

  if (session.status === "created") {
    return (
      <ReadyView
        actionError={interviews.actionError}
        onAbandon={interviews.abandon}
        onStart={interviews.start}
        saving={interviews.saving}
        session={session}
      />
    );
  }

  if (session.status === "in_progress") {
    return (
      <ActiveInterview
        actionError={interviews.actionError}
        onAbandon={interviews.abandon}
        onExpire={handleExpire}
        onFinish={interviews.finish}
        onSubmitAnswer={interviews.submitAnswer}
        saving={interviews.saving}
        session={session}
      />
    );
  }

  return (
    <div className="page-stack">
      <InterviewPageHeader />
      <ErrorState message="This interview reached a state this page does not render." onRetry={interviews.reload} />
    </div>
  );
}

function InterviewPageHeader() {
  return (
    <PageHeader
      description="A timed, judged rehearsal across the catalog. One session at a time, scored only by what the judge found."
      eyebrow="Interview studio"
      title="Practice how you will perform."
      action={<StatusPill tone="violet">Live judging</StatusPill>}
    />
  );
}

// ---------------------------------------------------------------- setup view

function ConfirmDialog({ title, message, confirmLabel, danger = false, saving, onCancel, onConfirm }) {
  const safeOptionRef = useRef(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  // Move focus to the safe option (the one that keeps the interview) so an
  // enter key can never confirm an exit by accident, and let Escape back out.
  // The listener is bound once on mount so a timer tick in the parent cannot
  // steal focus back from the option the learner chose.
  useEffect(() => {
    safeOptionRef.current?.focus();
    function onKeyDown(event) {
      if (event.key === "Escape") onCancelRef.current();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="confirm-backdrop">
      <div aria-labelledby="interview-confirm-title" aria-modal="true" className="confirm-dialog" role="dialog">
        <h3 id="interview-confirm-title">{title}</h3>
        <p className="confirm-message">{message}</p>
        <div className="interview-actions">
          <button className="button button-secondary" onClick={onCancel} ref={safeOptionRef} type="button">
            Keep coding
          </button>
          <button
            className={`button ${danger ? "button-danger" : "button-primary"}`}
            disabled={saving}
            onClick={onConfirm}
            type="button"
          >
            {saving ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function SetupView({ actionError, saving, history, onCreate, onOpenReport }) {
  const [role, setRole] = useState(DEFAULT_ROLE);
  const [level, setLevel] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [topic, setTopic] = useState("");
  const [questionCount, setQuestionCount] = useState(DEFAULT_QUESTION_COUNT);
  const [durationMinutes, setDurationMinutes] = useState(DEFAULT_DURATION_MINUTES);

  async function handleCreate(event) {
    event.preventDefault();
    await onCreate({
      role,
      level: level || null,
      difficulty: difficulty || null,
      topic: topic || null,
      questionCount,
      durationMinutes,
    });
  }

  return (
    <div className="page-stack">
      <InterviewPageHeader />

      <SectionCard
        title="Set up an interview"
        description="Calibration and filters only narrow the deterministic pick; the questions themselves are chosen for you, never faked."
      >
        <form className="interview-form" onSubmit={handleCreate}>
          <div className="interview-form-grid">
            <label className="interview-field">
              <span>Role</span>
              <input
                maxLength={80}
                onChange={(event) => setRole(event.target.value)}
                placeholder="What are you rehearsing for?"
                required
                type="text"
                value={role}
              />
            </label>
            <label className="interview-field">
              <span>Level <em>(optional)</em></span>
              <input
                maxLength={30}
                onChange={(event) => setLevel(event.target.value)}
                placeholder="e.g. mid, senior"
                type="text"
                value={level}
              />
            </label>
            <label className="interview-field">
              <span>Difficulty tier <em>(optional)</em></span>
              <select onChange={(event) => setDifficulty(event.target.value)} value={difficulty}>
                <option value="">Any tier</option>
                {DIFFICULTIES.map((tier) => (
                  <option key={tier} value={tier}>{tier}</option>
                ))}
              </select>
            </label>
            <label className="interview-field">
              <span>Topic <em>(optional)</em></span>
              <input
                maxLength={80}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="e.g. Arrays, Graphs"
                type="text"
                value={topic}
              />
            </label>
            <label className="interview-field">
              <span>Questions</span>
              <input
                max={MAX_QUESTION_COUNT}
                min={MIN_QUESTION_COUNT}
                onChange={(event) => setQuestionCount(event.target.value)}
                required
                type="number"
                value={questionCount}
              />
            </label>
            <label className="interview-field">
              <span>Duration (minutes)</span>
              <input
                max={MAX_DURATION_MINUTES}
                min={MIN_DURATION_MINUTES}
                onChange={(event) => setDurationMinutes(event.target.value)}
                required
                type="number"
                value={durationMinutes}
              />
            </label>
          </div>

          {actionError ? (
            <div className="inline-notice" role="alert">
              {actionError}
            </div>
          ) : null}

          <div className="interview-actions">
            <button className="button button-primary" disabled={saving} type="submit">
              <Play size={15} /> {saving ? "Creating…" : "Start interview"}
            </button>
            <span className="interview-hint">
              The clock starts only when you press start on the next screen.
            </span>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="Interview history" description="Every session you have opened, newest first.">
        {history.loading ? <LoadingState label="Loading your history" /> : null}
        {history.error ? <ErrorState message={history.error} onRetry={history.reload} /> : null}
        {history.data && history.data.items.length
          ? (
              <div className="history-list">
                {history.data.items.map((summary) => (
                  <HistoryRow key={summary.id} onOpenReport={onOpenReport} summary={summary} />
                ))}
              </div>
            )
          : null}
        {history.data && !history.data.items.length && !history.error ? (
          <EmptyState
            description="Finish your first session and its debrief will appear here."
            title="No interviews yet"
          />
        ) : null}
      </SectionCard>
    </div>
  );
}

function HistoryRow({ summary, onOpenReport }) {
  const duration = summary.duration_seconds ? `${Math.round(summary.duration_seconds / 60)} min` : null;
  const body = (
    <>
      <div className="submission-row-main">
        <strong>{summary.role || "Mock interview"}</strong>
        <span className="submission-row-meta">
          {formatSubmittedAt(summary.created_at)}
          {summary.difficulty ? ` · ${summary.difficulty}` : ""}
          {summary.topic ? ` · ${summary.topic}` : ""}
          {` · ${summary.question_count} ${summary.question_count === 1 ? "question" : "questions"}`}
          {duration ? ` · ${duration}` : ""}
        </span>
      </div>
      <div className="submission-row-meta">
        <StatusPill tone={interviewStatusTone(summary.status)}>{interviewStatusLabel(summary.status)}</StatusPill>
        {summary.score != null ? <strong>{summary.score}</strong> : null}
      </div>
    </>
  );

  if (summary.status !== "completed") {
    return <div className="history-row">{body}</div>;
  }
  return (
    <button
      aria-label={`Open the report for the ${summary.role || "interview"} on ${formatSubmittedAt(summary.created_at)}`}
      className="history-row history-row-action"
      onClick={() => onOpenReport(summary.id)}
      type="button"
    >
      {body}
      <ArrowRight size={15} />
    </button>
  );
}

// --------------------------------------------------------- created (ready) view

function ReadyView({ session, saving, actionError, onStart, onAbandon }) {
  const [confirmingAbandon, setConfirmingAbandon] = useState(false);

  return (
    <div className="page-stack">
      <PageHeader
        action={<StatusPill tone="neutral">{interviewStatusLabel(session.status)}</StatusPill>}
        description="The selection is recorded, so it cannot change between here and the clock."
        eyebrow="Mock interview"
        title="Your questions are ready."
      />
      <section className="interview-session-banner">
        <div className="interview-session-art"><Mic2 size={26} /></div>
        <div>
          <StatusPill tone="violet">Created · clock not started</StatusPill>
          <h3>{session.role}{session.level ? ` · ${session.level}` : ""}</h3>
          <p>
            {session.question_count} questions · {Math.round(session.duration_seconds / 60)} minutes
            {session.difficulty ? ` · ${session.difficulty} tier` : ""}
            {session.topic ? ` · topic ${session.topic}` : ""}
          </p>
        </div>
      </section>

      <SectionCard title="How this works" description="The rules of the rehearsal, before the clock starts.">
        <div className="interview-rules">
          <div className="interview-rule">
            <span className="stage-number">01</span>
            <p>The clock starts only when you press <strong>Start the clock</strong>. It is a server timer; this page just mirrors it.</p>
          </div>
          <div className="interview-rule">
            <span className="stage-number">02</span>
            <p>Work through the questions in any order. Each answer is run through the same judge the rest of the platform uses, hidden cases included.</p>
          </div>
          <div className="interview-rule">
            <span className="stage-number">03</span>
            <p>You may revise any question while time remains; every attempt is recorded. Your code stays on this page, so a refresh resumes the session but not your edits.</p>
          </div>
          <div className="interview-rule">
            <span className="stage-number">04</span>
            <p>The score is the percentage of questions the judge accepted. Ending on the timer, or by pressing Finish, both count; abandoning leaves no score.</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Question list" description="In the order they will be presented.">
        <div className="stage-list">
          {session.questions.map((question, index) => (
            <div className="stage-row" key={question.position}>
              <span className="stage-number">{String(index + 1).padStart(2, "0")}</span>
              <div className="stage-icon"><CheckCircle2 size={17} /></div>
              <div>
                <strong>{question.title}</strong>
                <p>{question.difficulty} · {question.topics.join(" · ")}</p>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {actionError ? (
        <div className="inline-notice" role="alert">{actionError}</div>
      ) : null}
      <div className="interview-actions">
        <button className="button button-primary" disabled={saving} onClick={() => onStart()} type="button">
          <Play size={15} /> {saving ? "Starting…" : "Start the clock"}
        </button>
        <button className="button button-quiet" disabled={saving} onClick={() => setConfirmingAbandon(true)} type="button">
          <XCircle size={15} /> Abandon interview
        </button>
      </div>

      {confirmingAbandon ? (
        <ConfirmDialog
          danger
          confirmLabel="Yes, abandon"
          message="Abandoning discards this session and its recorded questions without a score. This cannot be undone."
          onCancel={() => setConfirmingAbandon(false)}
          onConfirm={() => {
            setConfirmingAbandon(false);
            onAbandon();
          }}
          saving={saving}
          title="Abandon this interview?"
        />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------- active session

function ActiveInterview({ session, saving, actionError, onSubmitAnswer, onFinish, onAbandon, onExpire }) {
  // The countdown is a mirror of the server clock: it ticks from the
  // server-computed remaining seconds and, at zero, asks the API to finalise
  // the session. The client never decides that time has run out.
  const remaining = useInterviewCountdown(session.remaining_seconds, { enabled: true, onExpire });
  const [activePosition, setActivePosition] = useState(session.current_index ?? 0);
  const [languageByPosition, setLanguageByPosition] = useState({});
  const [codeByPosition, setCodeByPosition] = useState({});
  //: Which early exit the learner is confirming, if any. Finishing and
  //: abandoning are both irreversible, so both route through a confirmation.
  const [pendingExit, setPendingExit] = useState(null);

  const currentQuestion =
    session.questions.find((question) => question.position === activePosition) || session.questions[0];
  const loadProblem = useCallback(
    () => (currentQuestion?.slug ? problemApi.get(currentQuestion.slug) : Promise.resolve(null)),
    [currentQuestion?.slug],
  );
  const problem = useApiResource(loadProblem);

  const languages = useMemo(() => {
    const list = problem.data?.supported_languages;
    if (list && list.length) return list;
    return Object.keys(problem.data?.starter_code || {});
  }, [problem.data]);

  const language = languageByPosition[activePosition] || languages[0] || "python";
  const code = codeByPosition[activePosition];
  const starterCode = useMemo(() => {
    if (!problem.data) return "";
    return (
      problem.data.starter_code?.[language] ||
      Object.values(problem.data.starter_code || {})[0] ||
      ""
    );
  }, [problem.data, language]);

  // Seed the first language and starter code for a position exactly once, the
  // first time its problem statement arrives. Switching back to a question
  // keeps whatever the learner had typed there.
  useEffect(() => {
    if (!problem.data) return;
    const [first] = languages;
    setLanguageByPosition((previous) =>
      previous[activePosition] != null ? previous : { ...previous, [activePosition]: first || "python" },
    );
    setCodeByPosition((previous) => {
      if (previous[activePosition] != null) return previous;
      const starter = problem.data.starter_code?.[first] || Object.values(problem.data.starter_code || {})[0] || "";
      return { ...previous, [activePosition]: starter };
    });
  }, [problem.data, activePosition, languages]);

  function selectLanguage(languageId) {
    setLanguageByPosition((previous) => ({ ...previous, [activePosition]: languageId }));
  }

  function resetCode() {
    setCodeByPosition((previous) => ({ ...previous, [activePosition]: starterCode }));
  }

  async function handleSubmitCode() {
    const result = await onSubmitAnswer({ position: activePosition, language, sourceCode: code });
    // The API answers with the advanced pointer to the next unanswered question.
    if (result && result.status === "in_progress") {
      setActivePosition(result.current_index ?? activePosition);
    }
  }

  async function confirmExit() {
    const action = pendingExit;
    setPendingExit(null);
    if (action === "finish") await onFinish();
    else if (action === "abandon") await onAbandon();
  }

  const exitTitle = pendingExit === "abandon" ? "Abandon this interview?" : "Finish and score this interview?";
  const exitMessage =
    pendingExit === "abandon"
      ? "Abandoning discards the session without a score. Your answers stay in your submission history but this interview will have no result. This cannot be undone."
      : "Finishing ends the clock now and scores the questions the judge has already accepted. Questions you have not submitted are scored as unanswered. This cannot be undone.";
  const exitConfirmLabel = pendingExit === "abandon" ? "Yes, abandon" : "Finish and score";

  const answeredCount = session.questions.filter((question) => question.status === "submitted").length;
  const timerWarm = remaining != null && remaining < WARN_BELOW_SECONDS;

  if (!currentQuestion) {
    return (
      <div className="page-stack">
        <InterviewPageHeader />
        <ErrorState message="This session has no recorded questions." />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        action={<StatusPill tone="medium">{interviewStatusLabel(session.status)}</StatusPill>}
        description={`${answeredCount} of ${session.question_count} answered.`}
        eyebrow="Mock interview"
        title={session.role || "Interview session"}
      />

      <section className="interview-session-banner">
        <div className="interview-session-art"><Mic2 size={26} /></div>
        <div>
          <StatusPill tone={timerWarm ? "medium" : "violet"}>
            <Clock3 size={13} /> {formatRemainingSeconds(remaining)}
          </StatusPill>
          <h3>{session.role}{session.level ? ` · ${session.level}` : ""}</h3>
          <p>
            {session.difficulty ? `${session.difficulty} tier` : "Mixed tier"}
            {session.topic ? ` · topic ${session.topic}` : ""}
            {timerWarm ? " · finish soon" : ""}
          </p>
        </div>
      </section>

      <SectionCard title="Questions" description="Submitted questions keep their verdict; you can still revise them while the clock runs.">
        <div className="interview-question-nav" role="tablist" aria-label="Interview questions">
          {session.questions.map((question) => (
            <button
              aria-selected={activePosition === question.position}
              className={`interview-question-tab${activePosition === question.position ? " active" : ""}`}
              key={question.position}
              onClick={() => setActivePosition(question.position)}
              role="tab"
              type="button"
            >
              <span className="interview-question-tab-index">Q{question.position + 1}</span>
              <strong title={question.title}>{question.title}</strong>
              {question.status === "submitted" ? (
                <StatusPill tone={statusTone(question.verdict)}>{statusLabel(question.verdict)}</StatusPill>
              ) : (
                <StatusPill tone="neutral">Pending</StatusPill>
              )}
            </button>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title={currentQuestion.title}
        description={`${currentQuestion.difficulty} · ${currentQuestion.topics.join(" · ")}`}
      >
        <p className="constraints-copy">{currentQuestion.summary}</p>
        <div className="test-case-list">
          {(problem.data?.examples || []).map((example, index) => (
            <div className="test-case" key={`${example.input}-${index}`}>
              <div className="test-case-heading"><span>Example {index + 1}</span><CheckCircle2 size={15} /></div>
              <code>{example.input}</code>
              <code>{example.output}</code>
            </div>
          ))}
        </div>
        {problem.data?.constraints ? <p className="constraints-copy">{problem.data.constraints}</p> : null}
        {problem.error ? (
          <div className="inline-notice" role="alert">
            Could not load the statement. Your code is still judged against the recorded problem.
          </div>
        ) : null}
      </SectionCard>

      <SectionCard className="editor-card" title="Code workspace" description="A solution per question, graded by the same judge the rest of the platform uses.">
        <div className="editor-toolbar">
          <div className="language-tabs" role="tablist" aria-label="Programming language">
            {languages.map((item) => (
              <button
                aria-selected={language === item}
                className={`language-tab${language === item ? " active" : ""}`}
                key={item}
                onClick={() => selectLanguage(item)}
                role="tab"
                type="button"
              >
                {languageLabel(item)}
              </button>
            ))}
          </div>
          <button
            aria-label="Reset code"
            className="button button-quiet"
            disabled={!problem.data}
            onClick={resetCode}
            type="button"
          >
            <RotateCcw size={14} /> Reset
          </button>
        </div>
        <CodeEditor language={language} onChange={(next) => setCodeByPosition((previous) => ({ ...previous, [activePosition]: next }))} value={code} />
        <div className="editor-footer">
          <span>
            {currentQuestion.status === "submitted"
              ? `Verdict: ${statusLabel(currentQuestion.verdict)}${formatRuntime(currentQuestion.runtime_ms) ? ` · ${formatRuntime(currentQuestion.runtime_ms)}` : ""}`
              : "Not submitted yet"}
          </span>
          <div className="interview-actions">
            <button
              className="button button-primary"
              disabled={saving || !code?.trim() || !problem.data}
              onClick={handleSubmitCode}
              type="button"
            >
              <Gavel size={15} /> {saving ? "Judging…" : "Submit & judge"}
            </button>
            <button
              className="button button-quiet"
              disabled={saving}
              onClick={() => setPendingExit("finish")}
              type="button"
            >
              Finish interview
            </button>
            <button
              className="button button-quiet"
              disabled={saving}
              onClick={() => setPendingExit("abandon")}
              type="button"
            >
              <XCircle size={15} /> Abandon
            </button>
          </div>
        </div>
        {actionError ? (
          <div className="inline-notice" role="alert">
            {actionError}
          </div>
        ) : null}
      </SectionCard>

      {pendingExit ? (
        <ConfirmDialog
          danger={pendingExit === "abandon"}
          confirmLabel={exitConfirmLabel}
          message={exitMessage}
          onCancel={() => setPendingExit(null)}
          onConfirm={confirmExit}
          saving={saving}
          title={exitTitle}
        />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ report view

function ReportView({ report, error, errorStatus, loading, onClose, onRetry, onStartAnother, fromHistory }) {
  return (
    <div className="page-stack">
      <PageHeader
        action={
          fromHistory ? (
            <button className="button button-quiet" onClick={onClose} type="button">
              <ArrowLeft size={15} /> Back to history
            </button>
          ) : null
        }
        description="A deterministic reading of what the judge found, nothing estimated."
        eyebrow="Mock interview · debrief"
        title="Your interview report"
      />

      {loading ? <LoadingState label="Building your report" /> : null}

      {error && errorStatus === 404 ? (
        <div className="inline-notice" role="alert">
          This interview is not in your history. The API will not say whether it
          is missing or belongs to someone else.
        </div>
      ) : null}
      {error && errorStatus === 409 ? (
        <div className="inline-notice" role="alert">
          This interview is not completed yet; there is nothing to report until
          it finishes.
        </div>
      ) : null}
      {error && errorStatus !== 404 && errorStatus !== 409 ? <ErrorState message={error} onRetry={onRetry} /> : null}

      {report ? (
        <>
          <SectionCard title="Score" description="Accepted answers over the session's questions, as a percentage.">
            <div className="report-score">
              <strong>{report.score}</strong>
              <span>of 100</span>
              {report.timed_out ? <StatusPill tone="medium">Time ran out</StatusPill> : <StatusPill tone="success">Finished on time</StatusPill>}
            </div>
          </SectionCard>

          <dl className="submission-facts">
            <div>
              <dt><CheckCircle2 size={14} /> Answered</dt>
              <dd>{report.questions_answered} of {report.question_count}</dd>
            </div>
            <div>
              <dt><Gavel size={14} /> Accepted</dt>
              <dd>{report.questions_accepted}</dd>
            </div>
            <div>
              <dt><Clock3 size={14} /> Time used</dt>
              <dd>{formatRemainingSeconds(report.duration_used_seconds)}</dd>
            </div>
          </dl>

          <SectionCard title="Per-question breakdown" description="Each row is the question as the judge left it.">
            <div className="history-list">
              {report.questions.map((question) => (
                <div className="report-question" key={question.position}>
                  <div className="report-question-head">
                    <div className="submission-row-main">
                      <strong>
                        <span className="report-question-index">Q{question.position + 1}</span> {question.title}
                      </strong>
                      <span className="submission-row-meta">
                        {question.difficulty} · {question.topics.join(" · ")}
                        {question.status === "submitted" && question.language ? ` · ${languageLabel(question.language)}` : ""}
                        {question.attempts > 0 ? ` · ${question.attempts} ${question.attempts === 1 ? "attempt" : "attempts"}` : ""}
                      </span>
                    </div>
                    <div className="submission-row-meta">
                      {question.status === "submitted" ? (
                        <StatusPill tone={statusTone(question.verdict)}>{statusLabel(question.verdict)}</StatusPill>
                      ) : (
                        <StatusPill tone="neutral">Unanswered</StatusPill>
                      )}
                      {formatCaseCounts(question) ? <span>{formatCaseCounts(question)}</span> : null}
                      {formatRuntime(question.runtime_ms) ? <span>{formatRuntime(question.runtime_ms)}</span> : null}
                    </div>
                  </div>
                  {question.answered_seconds_into_session != null ? (
                    <p className="report-question-timing">
                      First answer {formatRemainingSeconds(question.answered_seconds_into_session)} into the session.
                    </p>
                  ) : null}
                  {question.status === "submitted" && question.submission_id ? (
                    <DiagnosisPanel status={question.verdict} submissionId={question.submission_id} />
                  ) : null}
                </div>
              ))}
            </div>
          </SectionCard>

          <div className="interview-actions">
            <button className="button button-primary" onClick={onStartAnother} type="button">
              Start a new interview <ArrowRight size={15} />
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}