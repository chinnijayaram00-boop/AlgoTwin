import { ArrowLeft, Braces, CheckCircle2, Clock3, FlaskConical, Play, RotateCcw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import CodeEditor from "../features/problems/CodeEditor";
import ProblemProgressPanel from "../features/progress/ProblemProgressPanel";
import { ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { problemApi } from "../services/platformService";

const languages = [
  { id: "javascript", label: "JavaScript" },
  { id: "python", label: "Python" },
];

export default function WorkspacePage() {
  const { slug } = useParams();
  const loadProblem = useCallback(() => problemApi.get(slug), [slug]);
  const { data: problem, error, loading, reload } = useApiResource(loadProblem);
  const [language, setLanguage] = useState("javascript");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!problem) return;
    const starterCode = problem.starter_code?.[language] || Object.values(problem.starter_code || {})[0] || "";
    setCode(starterCode);
  }, [language, problem]);

  if (loading) return <LoadingState label="Loading problem workspace" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!problem) return null;

  return (
    <div className="page-stack workspace-page">
      <Link className="back-link" to="/problems"><ArrowLeft size={15} /> Back to problems</Link>
      <PageHeader
        description={problem.summary}
        eyebrow={`${problem.difficulty} · ${problem.topics.join(" · ")}`}
        title={problem.title}
        action={<StatusPill tone="success">Workspace ready</StatusPill>}
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
            <span><Clock3 size={14} /> Time limit not configured</span>
            <button className="button button-primary" onClick={() => setNotice("Execution is intentionally disabled until a sandboxed runner is connected.")} type="button">
              <Play size={15} /> Run test cases
            </button>
          </div>
          {notice ? <div className="inline-notice"><FlaskConical size={15} /> {notice}</div> : null}
        </SectionCard>

        <div className="workspace-side-column">
          <SectionCard title="Your progress" description="Stored against your account for this problem.">
            <ProblemProgressPanel problemId={problem.id} />
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
          <SectionCard title="Analysis" description="Complexity signals will come from the runner.">
            <div className="analysis-list">
              <div><span>Time</span><strong>Not measured</strong></div>
              <div><span>Space</span><strong>Not measured</strong></div>
              <div><span>AI explanation</span><strong>Provider pending</strong></div>
            </div>
            <div className="analysis-note"><Sparkles size={15} /> Connect the AI provider boundary to generate a guided explanation after a run.</div>
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
