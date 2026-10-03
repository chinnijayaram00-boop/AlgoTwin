import { ArrowRight, GitCompareArrows, Gauge, Scale, Timer, Zap } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";
import { NOT_MEASURED, algorithmApi, formatMeasurement } from "../features/visualization/algorithmService";

/**
 * The comparison view.
 *
 * Two rules this page exists to keep.
 *
 * **One input.** The picker selects algorithms; the input box is a single field that
 * every side receives. There is deliberately no per-algorithm input, because the only
 * thing that makes a comparison a comparison is that the sides were handed the same
 * values. The API enforces it structurally and the UI mirrors that rather than
 * offering a way around it.
 *
 * **Nothing is invented.** A measurement the platform did not take renders as
 * "Not measured" -- never as `0`, and never as a dash that could be read as a small
 * number. Every requested side stays on screen whether or not it produced a result,
 * because a comparison that quietly dropped a failed side would be indistinguishable
 * from one where that side simply happened to be slow.
 */
export default function ComparePage() {
  const loadAlgorithms = useCallback(() => platformApi.algorithms(), []);
  const { data, error, loading, reload } = useApiResource(loadAlgorithms);
  const algorithms = useMemo(() => data?.items || [], [data]);

  const [chosen, setChosen] = useState([]);
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [runError, setRunError] = useState("");
  const [running, setRunning] = useState(false);

  // The pairings the API would accept: only algorithms sharing a comparison group.
  // Derived from the catalog rather than hardcoded, so a new algorithm joins the
  // right groups without a second list here that could disagree with the backend.
  const groups = useMemo(() => {
    const byGroup = new Map();
    for (const algorithm of algorithms) {
      if (!byGroup.has(algorithm.comparison_group)) byGroup.set(algorithm.comparison_group, []);
      byGroup.get(algorithm.comparison_group).push(algorithm);
    }
    return byGroup;
  }, [algorithms]);

  const comparableGroups = useMemo(
    () => [...groups.entries()].filter(([, members]) => members.length >= 2),
    [groups],
  );

  const toggle = (algorithmId, group) => {
    setResult(null);
    setRunError("");
    setChosen((current) => {
      if (current.some((entry) => entry.id === algorithmId)) {
        return current.filter((entry) => entry.id !== algorithmId);
      }
      // Choosing an algorithm from another group replaces the selection rather than
      // mixing them. A mixed selection could only produce a 422, and letting the
      // learner assemble one by hand is a worse experience than being switched.
      const sameGroup = current.length ? current[0].group : group;
      if (group !== sameGroup) {
        const member = algorithms.find((algorithm) => algorithm.id === algorithmId);
        setInput(member?.sample_input || "");
        return [{ id: algorithmId, group }];
      }
      if (current.length >= 4) return current;
      return [...current, { id: algorithmId, group }];
    });
  };

  const runComparison = async () => {
    setRunning(true);
    setRunError("");
    setResult(null);
    try {
      const payload = await algorithmApi.compare({
        algorithmIds: chosen.map((entry) => entry.id),
        input,
      });
      setResult(payload);
    } catch (requestError) {
      setRunError(requestError.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        description="Make trade-offs explicit with a comparison model that can grow alongside your practice history."
        eyebrow="Decision workspace"
        title="Compare before you commit."
        action={<Link className="button button-primary" to="/problems"><span>Choose a problem</span><ArrowRight size={16} /></Link>}
      />
      <section className="feature-hero compare-hero">
        <div className="feature-hero-icon"><GitCompareArrows size={24} /></div>
        <div>
          <span className="eyebrow">One input, many approaches</span>
          <h3>Only algorithms that solve the same task can be compared.</h3>
          <p>
            Sorting six algorithms against each other is meaningful. Sorting against Kadane's is not,
            because the two are not competing on anything. The API refuses that pairing, and the
            picker below only offers the ones it would accept.
          </p>
        </div>
        <StatusPill tone="neutral">
          {comparableGroups.length} comparable group{comparableGroups.length === 1 ? "" : "s"}
        </StatusPill>
      </section>

      {loading ? <LoadingState label="Loading algorithm registry" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}

      {!loading && !error ? (
        <>
          <SectionCard
            title="Pick two to four algorithms"
            description="Every side receives the one input below."
          >
            {comparableGroups.length ? (
              comparableGroups.map(([group, members]) => (
                <div className="compare-group" key={group}>
                  <span className="compare-group-label">{group}</span>
                  <div className="algorithm-grid">
                    {members.map((algorithm) => {
                      const isChosen = chosen.some((entry) => entry.id === algorithm.id);
                      const atLimit = chosen.length >= 4 && !isChosen;
                      return (
                        <button
                          aria-pressed={isChosen}
                          className={`algorithm-card${isChosen ? " is-selected" : ""}`}
                          disabled={atLimit}
                          key={algorithm.id}
                          onClick={() => toggle(algorithm.id, group)}
                          type="button"
                        >
                          <strong>{algorithm.name}</strong>
                          <span className="algorithm-category">{algorithm.time_complexity || "n/a"}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                description="No group has two algorithms yet."
                title="Nothing to compare"
              />
            )}
          </SectionCard>

          <SectionCard title="The shared input" description="Applied to every selected algorithm.">
            <label className="field-group">
              <span className="field-label">Input</span>
              <textarea
                className="field-input code-input"
                onChange={(event) => setInput(event.target.value)}
                rows={4}
                value={input}
              />
              <span className="field-hint">
                {chosen.length
                  ? algorithms.find((algorithm) => algorithm.id === chosen[0].id)?.input_hint
                  : "Select an algorithm to see its input format."}
              </span>
            </label>
            <div className="trace-actions">
              <button
                className="button button-primary"
                disabled={running || chosen.length < 2 || !input.trim()}
                onClick={runComparison}
                type="button"
              >
                <GitCompareArrows size={16} />
                <span>{running ? "Comparing" : "Compare"}</span>
              </button>
              <span className="field-hint">
                {chosen.length < 2
                  ? "Pick at least two algorithms."
                  : `Comparing ${chosen.length} on one input.`}
              </span>
            </div>
          </SectionCard>

          {running ? <LoadingState label="Running every side" /> : null}
          {runError ? <ErrorState message={runError} onRetry={runComparison} /> : null}

          {result ? <ComparisonResult result={result} /> : null}
        </>
      ) : null}

      <div className="comparison-layout">
        <SectionCard title="What the numbers mean" description="Measured here, not estimated.">
          <div className="comparison-table">
            <div className="comparison-row">
              <span>Runtime</span>
              <p>The median of repeated in-process runs of the same input. It says nothing about complexity on its own.</p>
            </div>
            <div className="comparison-row">
              <span>Operations</span>
              <p>Counted by the algorithm as it ran. This is the figure that explains the runtime.</p>
            </div>
            <div className="comparison-row">
              <span>Memory</span>
              <p>Peak worker memory, where the platform can measure it. Where it cannot, the cell says so.</p>
            </div>
            <div className="comparison-row">
              <span>Same input</span>
              <p>Every side is handed the one input above, and the response echoes it back as the evidence.</p>
            </div>
          </div>
        </SectionCard>
        <div className="comparison-side">
          <Signal icon={Timer} label="Runtime" value={NOT_MEASURED} />
          <Signal icon={Gauge} label="Memory" value={NOT_MEASURED} />
          <Signal icon={Zap} label="Pass rate" value="Not applicable" />
          <Signal icon={Scale} label="Recommendation" value="From the counters" />
        </div>
      </div>
    </div>
  );
}

/**
 * The measured table.
 *
 * Every requested side appears, in the order it was asked for, including one that
 * failed. `complete` drives the banner: when it is false the UI says a side did not
 * run rather than presenting the surviving columns as if they were the whole
 * comparison.
 */
function ComparisonResult({ result }) {
  const sides = result.sides || [];
  const fastest = fastestSide(sides);

  return (
    <SectionCard
      title="Measured on the same input"
      description={`Group: ${result.comparison_group} · ${result.input.split("\n").length} input line(s)`}
      className="comparison-result"
    >
      {result.complete === false ? (
        <p className="comparison-warning" role="status">
          At least one side did not run. The figures below are only for the sides that did.
        </p>
      ) : null}
      <div className="comparison-grid">
        {sides.map((side) => (
          <div className="comparison-column" key={side.algorithm.id}>
            <div className="comparison-column-header">
              <strong>{side.algorithm.name}</strong>
              <StatusPill tone={side.status === "ok" ? "success" : "warning"}>{side.status}</StatusPill>
            </div>
            <div className="comparison-metrics">
              <Metric label="Runtime" value={formatMeasurement(side.runtime_ms, " ms", 3)} />
              <Metric label="Peak memory" value={formatMeasurement(side.peak_memory_mb, " MB")} />
              <Metric label="Frames" value={side.frame_count ?? NOT_MEASURED} />
              <Metric label="Repetitions" value={side.repetitions ?? NOT_MEASURED} />
            </div>
            <div className="comparison-counters">
              {Object.entries(side.metrics || {}).map(([name, value]) => (
                <span className="metric-chip" key={name}>
                  <code>{name.replace(/_/g, " ")}</code>
                  <strong>{value}</strong>
                </span>
              ))}
            </div>
            {side.result ? <p className="comparison-answer">Result: {side.result}</p> : null}
            {side.error ? <p className="comparison-error">{side.error}</p> : null}
            {side.status === "ok" && side.algorithm.id === fastest ? (
              <p className="comparison-note">Fastest measured side.</p>
            ) : null}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

/** The id of the side with the smallest measured runtime, or `null`. */
function fastestSide(sides) {
  const measured = sides.filter(
    (side) => side.status === "ok" && Number.isFinite(Number(side.runtime_ms)) && Number(side.runtime_ms) > 0,
  );
  if (!measured.length) return null;
  return measured.reduce((best, side) => (Number(side.runtime_ms) < Number(best.runtime_ms) ? side : best))
    .algorithm.id;
}

function Metric({ label, value }) {
  return (
    <div className="comparison-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Signal({ icon: Icon, label, value }) {
  return (
    <div className="signal-card"><Icon size={17} /><span>{label}</span><strong>{value}</strong></div>
  );
}
