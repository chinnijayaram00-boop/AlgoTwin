import { ArrowRight, GitCompareArrows, Gauge, Scale, Timer, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";

const comparisonRows = [
  { label: "Approach", value: "Register two solutions and compare their trade-offs." },
  { label: "Complexity", value: "Time and space will be populated from runner traces." },
  { label: "Readability", value: "Human ratings will remain separate from measured signals." },
  { label: "Decision support", value: "AI guidance will be grounded in the selected problem." },
];

export default function ComparePage() {
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
          <span className="eyebrow">Comparison contract</span>
          <h3>One problem, multiple ways to solve it.</h3>
          <p>Select candidate solutions, run identical test cases, and inspect measured signals side by side.</p>
        </div>
        <StatusPill tone="neutral">Runner pending</StatusPill>
      </section>
      <div className="comparison-layout">
        <SectionCard title="What will be compared" description="The foundation defines the decision surface without inventing results.">
          <div className="comparison-table">
            {comparisonRows.map((row) => (
              <div className="comparison-row" key={row.label}>
                <span>{row.label}</span>
                <p>{row.value}</p>
              </div>
            ))}
          </div>
        </SectionCard>
        <div className="comparison-side">
          <Signal icon={Timer} label="Runtime" value="Not measured" />
          <Signal icon={Gauge} label="Memory" value="Not measured" />
          <Signal icon={Zap} label="Pass rate" value="Not measured" />
          <Signal icon={Scale} label="Recommendation" value="Pending runner" />
        </div>
      </div>
    </div>
  );
}

function Signal({ icon: Icon, label, value }) {
  return (
    <div className="signal-card"><Icon size={17} /><span>{label}</span><strong>{value}</strong></div>
  );
}
