import { Binary, Box, GitBranch, Network, PlayCircle, Sparkles, Waypoints } from "lucide-react";
import { useCallback } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";

export default function VisualizerPage() {
  const loadAlgorithms = useCallback(() => platformApi.algorithms(), []);
  const { data, error, loading, reload } = useApiResource(loadAlgorithms);
  const algorithms = data?.items || [];

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
          <span className="eyebrow">Visualization contract</span>
          <h3>Frame-by-frame explanations are next.</h3>
          <p>The API already exposes an algorithm registry. A sandboxed execution worker will produce normalized frames for the timeline UI.</p>
        </div>
        <StatusPill tone="neutral">Registry: {algorithms.length} algorithms</StatusPill>
      </section>
      {loading ? <LoadingState label="Loading algorithm registry" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!loading && !error ? (
        algorithms.length ? (
          <div className="algorithm-grid">
            {algorithms.map((algorithm) => (
              <SectionCard key={algorithm.id} title={algorithm.name} description={algorithm.category}>
                <div className="algorithm-complexity"><span>Time {algorithm.time_complexity || "—"}</span><span>Space {algorithm.space_complexity || "—"}</span></div>
              </SectionCard>
            ))}
          </div>
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
        <Capability icon={Box} title="Execution trace" detail="A future runner boundary keeps untrusted code out of the API." />
        <Capability icon={PlayCircle} title="Step controls" detail="Play, pause, and inspect each transition in the browser." />
        <Capability icon={Sparkles} title="Narrated insight" detail="AI explanations can be attached to a specific visual frame." />
      </div>
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
