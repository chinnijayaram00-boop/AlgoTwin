import { Binary, Box, GitBranch, Network, PlayCircle, Sparkles, Waypoints } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";
import { algorithmApi } from "../features/visualization/algorithmService";
import { FrameRenderer, MetricReadout, PointerReadout } from "../features/visualization/FrameRenderer";
import { TimelineControls } from "../features/visualization/TimelineControls";
import { useFrameTimeline } from "../features/visualization/useFrameTimeline";

/**
 * The algorithm lab.
 *
 * Two halves on one page, and the split is the point. The catalog is public, so it
 * loads for anyone; the trace is a POST that starts a worker on the API, so it needs
 * a session and reports its own loading, empty, and failure states rather than
 * pretending to animate something.
 *
 * The timeline state lives here, not in the controls, so the renderer draws the same
 * frame the scrubber is pointing at.
 */
export default function VisualizerPage() {
  const loadAlgorithms = useCallback(() => platformApi.algorithms(), []);
  const { data, error, loading, reload } = useApiResource(loadAlgorithms);
  const algorithms = useMemo(() => data?.items || [], [data]);

  const [selectedId, setSelectedId] = useState("");
  const [input, setInput] = useState("");
  const [trace, setTrace] = useState(null);
  const [traceError, setTraceError] = useState("");
  const [tracing, setTracing] = useState(false);

  const selected = useMemo(
    () => algorithms.find((algorithm) => algorithm.id === selectedId) || null,
    [algorithms, selectedId],
  );

  // Changing the algorithm clears the previous timeline immediately. Keeping it would
  // show merge sort's frames under a bubble sort card for as long as it took the
  // learner's next click -- and a stale frame is worse than an empty one, because it
  // looks like a result.
  const chooseAlgorithm = (algorithmId) => {
    setSelectedId(algorithmId);
    setTrace(null);
    setTraceError("");
    const chosen = algorithms.find((algorithm) => algorithm.id === algorithmId);
    if (chosen) setInput(chosen.sample_input);
  };

  const runTrace = async () => {
    if (!selected) return;
    setTracing(true);
    setTraceError("");
    try {
      const result = await algorithmApi.visualize(selected.id, { input });
      setTrace(result);
    } catch (requestError) {
      setTrace(null);
      setTraceError(requestError.message);
    } finally {
      setTracing(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        description="Make state changes visible before you memorize the implementation."
        eyebrow="Algorithm lab"
        title="See the machine think."
        action={<Link className="button button-primary" to="/compare"><GitBranch size={16} /> Compare approaches</Link>}
      />
      <section className="feature-hero visualizer-hero">
        <div className="feature-hero-icon"><Waypoints size={24} /></div>
        <div>
          <span className="eyebrow">Live execution</span>
          <h3>Every frame is a state the algorithm was really in.</h3>
          <p>
            Frames come from a generator that yields as the algorithm works, in a sandboxed worker
            with its own wall clock. Nothing is reconstructed afterwards, and a run the frame ceiling
            cut short says so instead of looking complete.
          </p>
        </div>
        <StatusPill tone="neutral">Registry: {algorithms.length} algorithms</StatusPill>
      </section>
      {loading ? <LoadingState label="Loading algorithm registry" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!loading && !error ? (
        algorithms.length ? (
          <>
            <SectionCard
              title="Choose an algorithm"
              description="Each card names a real implementation the platform can run."
            >
              <div className="algorithm-grid">
                {algorithms.map((algorithm) => (
                  <button
                    aria-pressed={algorithm.id === selectedId}
                    className={`algorithm-card${algorithm.id === selectedId ? " is-selected" : ""}`}
                    key={algorithm.id}
                    onClick={() => chooseAlgorithm(algorithm.id)}
                    type="button"
                  >
                    <strong>{algorithm.name}</strong>
                    <span className="algorithm-category">{algorithm.category}</span>
                    <div className="algorithm-complexity">
                      <span>Time {algorithm.time_complexity || "n/a"}</span>
                      <span>Space {algorithm.space_complexity || "n/a"}</span>
                    </div>
                    {algorithm.is_stable === true ? <StatusPill tone="success">Stable</StatusPill> : null}
                    {algorithm.is_stable === false ? <StatusPill tone="warning">Not stable</StatusPill> : null}
                  </button>
                ))}
              </div>
            </SectionCard>

            {selected ? (
              <SectionCard
                title={selected.name}
                description={selected.summary}
                className="trace-card"
              >
                <div className="algorithm-complexity">
                  <span>Time {selected.time_complexity || "n/a"}</span>
                  <span>Space {selected.space_complexity || "n/a"}</span>
                  {selected.comparison_group ? (
                    <span>Group {selected.comparison_group}</span>
                  ) : null}
                </div>

                <label className="field-group">
                  <span className="field-label">Input</span>
                  <textarea
                    className="field-input code-input"
                    onChange={(event) => setInput(event.target.value)}
                    rows={4}
                    value={input}
                  />
                  <span className="field-hint">{selected.input_hint}</span>
                </label>

                <div className="trace-actions">
                  <button
                    className="button button-primary"
                    disabled={tracing || !input.trim()}
                    onClick={runTrace}
                    type="button"
                  >
                    <PlayCircle size={16} />
                    <span>{tracing ? "Tracing" : "Run"}</span>
                  </button>
                  {trace?.truncated ? <StatusPill tone="warning">Capped timeline</StatusPill> : null}
                </div>

                {tracing ? <LoadingState label="Running the algorithm" /> : null}
                {traceError ? <ErrorState message={traceError} onRetry={runTrace} /> : null}

                {trace ? <TracePanel trace={trace} /> : null}
              </SectionCard>
            ) : (
              <EmptyState
                description="Pick one of the algorithms above to trace it on an input of your own."
                title="Choose an algorithm to start"
                action={<Link className="button button-secondary" to="/compare"><Binary size={16} /> View comparison model</Link>}
              />
            )}
          </>
        ) : (
          <EmptyState
            description="Algorithm executors will appear here as they are registered."
            title="The registry is intentionally empty"
            action={<Link className="button button-secondary" to="/compare"><Binary size={16} /> View comparison model</Link>}
          />
        )
      ) : null}
      <div className="capability-grid">
        <Capability icon={Network} title="State timeline" detail="Normalized frames for pointers, stacks, queues, and graphs." />
        <Capability icon={Box} title="Sandboxed execution" detail="A supervised worker keeps a traced algorithm out of the API process." />
        <Capability icon={PlayCircle} title="Step controls" detail="Play, pause, and inspect each transition in the browser." />
        <Capability icon={Sparkles} title="Honest counters" detail="Operation counts are recorded by the algorithm, never estimated." />
      </div>
    </div>
  );
}

/**
 * The drawn frame plus its controls.
 *
 * Split out so the timeline hook is called in exactly one place in the tree. If the
 * page and the controls each called it, the page would render a frame from one index
 * while the scrubber moved another.
 */
function TracePanel({ trace }) {
  const frames = trace.frames || [];
  const timeline = useFrameTimeline(frames.length);
  const frame = frames[timeline.index];

  return (
    <div className="trace-panel">
      <FrameRenderer frame={frame} stateKind={trace.algorithm?.state_kind} />
      <div className="trace-side">
        <PointerReadout pointers={frame?.state?.pointers} />
        <MetricReadout metrics={frame?.state?.metrics} />
        {trace.result ? (
          <div className="trace-result">
            <span className="pointer-readout-label">Result</span>
            <strong>{trace.result}</strong>
          </div>
        ) : null}
        <div className="trace-meta">
          <span>{frames.length} frames</span>
          {trace.duration_ms !== null && trace.duration_ms !== undefined ? (
            <span>{trace.duration_ms.toFixed(1)} ms in the worker</span>
          ) : null}
          <span>Whole run: {trace.truncated ? "capped" : "complete"}</span>
        </div>
      </div>
      <TimelineControls timeline={timeline} explanation={frame?.explanation} />
    </div>
  );
}

function Capability({ icon: Icon, title, detail }) {
  return (
    <div className="capability-card">
      <Icon size={18} />
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}
