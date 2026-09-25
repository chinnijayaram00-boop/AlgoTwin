import { Activity, BrainCircuit, Clock3, Target } from "lucide-react";
import { useCallback } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";

const levels = ["Easy", "Medium", "Hard"];

export default function AnalyticsPage() {
  const loadSummary = useCallback(() => platformApi.dashboardSummary(), []);
  const { data, error, loading, reload } = useApiResource(loadSummary);
  const chartData = levels.map((level) => ({ level, count: data?.by_difficulty?.[level] || 0 }));

  return (
    <div className="page-stack">
      <PageHeader
        description="Analytics will combine catalog exposure, problem completion, complexity trends, and interview reflection."
        eyebrow="Learning intelligence"
        title="Notice the shape of your progress."
      />
      {loading ? <LoadingState label="Loading learning signals" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!loading && !error ? (
        <>
          <div className="metrics-grid analytics-metrics">
            <InsightCard icon={Target} label="Catalog coverage" value={data?.total_problems ?? 0} detail="Published problems" />
            <InsightCard icon={Activity} label="Practice trend" value="Pending" detail="Requires progress model" />
            <InsightCard icon={Clock3} label="Time signal" value="Pending" detail="Requires runner traces" />
            <InsightCard icon={BrainCircuit} label="AI reflection" value="Pending" detail="Requires provider" />
          </div>
          <SectionCard description="This chart uses the current catalog response; learner-specific metrics will be added after authentication." title="Catalog distribution">
            {data?.total_problems ? (
              <div className="chart-wrap analytics-chart">
                <ResponsiveContainer height={300} width="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#25304a" strokeDasharray="3 3" vertical={false} />
                    <XAxis axisLine={false} dataKey="level" tick={{ fill: "#8d9ab5", fontSize: 12 }} tickLine={false} />
                    <YAxis allowDecimals={false} axisLine={false} tick={{ fill: "#8d9ab5", fontSize: 12 }} tickLine={false} />
                    <Tooltip contentStyle={{ background: "#151d32", border: "1px solid #2b3857", borderRadius: 12, color: "#f4f7ff" }} />
                    <Bar dataKey="count" fill="#3cc9b0" name="Problems" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState description="Publish problems to unlock the catalog distribution." title="No data to analyze" />
            )}
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}

function InsightCard({ icon: Icon, label, value, detail }) {
  return (
    <div className="metric-card insight-card">
      <div className="metric-icon"><Icon size={18} /></div>
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}
