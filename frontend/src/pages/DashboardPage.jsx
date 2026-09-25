import {
  Activity,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  Code2,
  Sparkles,
  Trophy,
} from "lucide-react";
import { useCallback } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";
import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";

const difficultyOrder = ["Easy", "Medium", "Hard"];

export default function DashboardPage() {
  const loadSummary = useCallback(() => platformApi.dashboardSummary(), []);
  const loadHealth = useCallback(() => platformApi.health(), []);
  const { data: summary, error, loading, reload } = useApiResource(loadSummary);
  const { data: health } = useApiResource(loadHealth);
  const chartData = difficultyOrder.map((difficulty) => ({
    difficulty,
    problems: summary?.by_difficulty?.[difficulty] || 0,
  }));

  return (
    <div className="page-stack">
      <PageHeader
        description="A calm command center for your algorithms, patterns, and interview preparation."
        eyebrow="Welcome back, learner"
        title="Make every problem count."
        action={
          <Link className="button button-primary" to="/problems">
            Open problem library <ArrowRight size={16} />
          </Link>
        }
      />

      <section className="hero-panel">
        <div className="hero-copy">
          <div className="hero-kicker">
            <span className="pulse-icon"><Activity size={15} /></span>
            Your learning system is ready
          </div>
          <h3>Build intuition before you optimize.</h3>
          <p>
            ALgotwin connects concept learning, deliberate practice, and technical interview confidence in one focused workspace.
          </p>
          <div className="hero-actions">
            <Link className="button button-light" to="/visualizer">
              Explore the visualizer <ArrowRight size={16} />
            </Link>
            <span className="hero-note">Foundation release · sandboxed execution coming next</span>
          </div>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit-core"><BrainCircuit size={30} /></div>
          <span className="orbit-node node-one" />
          <span className="orbit-node node-two" />
          <span className="orbit-node node-three" />
        </div>
      </section>

      <div className="metrics-grid">
        <MetricCard icon={BookOpenCheck} label="Catalog problems" value={summary?.total_problems ?? "—"} detail="Published foundations" />
        <MetricCard icon={Code2} label="Practice mode" value="Editor" detail="Monaco workspace" />
        <MetricCard icon={Trophy} label="Progress tracking" value="Next" detail="Auth-ready model" />
        <MetricCard icon={Sparkles} label="AI explanations" value="Next" detail="Provider boundary" />
      </div>

      {loading ? <LoadingState label="Loading your catalog" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}

      <div className="dashboard-grid">
        <SectionCard description="Actual counts from the current API catalog." title="Catalog signal">
          {summary && summary.total_problems > 0 ? (
            <div className="chart-wrap">
              <ResponsiveContainer height={250} width="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="#25304a" strokeDasharray="3 3" vertical={false} />
                  <XAxis axisLine={false} dataKey="difficulty" tick={{ fill: "#8d9ab5", fontSize: 12 }} tickLine={false} />
                  <YAxis allowDecimals={false} axisLine={false} tick={{ fill: "#8d9ab5", fontSize: 12 }} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: "#151d32", border: "1px solid #2b3857", borderRadius: 12, color: "#f4f7ff" }}
                    cursor={{ fill: "rgba(124, 108, 255, 0.1)" }}
                  />
                  <Bar dataKey="problems" fill="#7c6cff" name="Problems" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState description="Publish a problem to see your catalog signal here." title="No catalog data yet" />
          )}
        </SectionCard>

        <SectionCard description="The next layers are separated and ready for implementation." title="Learning loop">
          <div className="learning-loop">
            <LoopStep icon={BookOpenCheck} index="01" label="Learn" detail="Patterns and concepts" />
            <LoopStep icon={Code2} index="02" label="Practice" detail="Editor and test cases" />
            <LoopStep icon={BrainCircuit} index="03" label="Understand" detail="AI explanations" />
            <LoopStep icon={Trophy} index="04" label="Perform" detail="Interview simulation" />
          </div>
          <div className="status-line">
            <StatusPill tone={health?.status === "ok" ? "success" : "neutral"}>
              {health?.status === "ok" ? "API connected" : "API status checking"}
            </StatusPill>
            <span>Local foundation is available.</span>
          </div>
        </SectionCard>
      </div>

      <section className="next-step-banner">
        <div>
          <span className="eyebrow">Recommended next step</span>
          <h3>Pick a pattern and make it yours.</h3>
          <p>Start with an easy problem, then compare approaches before writing the optimized solution.</p>
        </div>
        <Link className="button button-secondary" to="/problems?difficulty=Easy">
          Browse easy problems <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail }) {
  return (
    <div className="metric-card">
      <div className="metric-icon"><Icon size={18} /></div>
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}

function LoopStep({ icon: Icon, index, label, detail }) {
  return (
    <div className="loop-step">
      <div className="loop-step-top"><span>{index}</span><Icon size={16} /></div>
      <strong>{label}</strong>
      <p>{detail}</p>
    </div>
  );
}
