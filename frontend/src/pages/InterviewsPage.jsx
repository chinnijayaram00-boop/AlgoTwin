import { ArrowRight, CheckCircle2, Clock3, MessageSquareText, Mic2, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";

const interviewStages = [
  { icon: UsersRound, title: "Role calibration", detail: "Choose role, level, and target interview track." },
  { icon: MessageSquareText, title: "Problem conversation", detail: "Practice clarifying questions before implementation." },
  { icon: Mic2, title: "Live coding", detail: "Use the same editor and test-case workflow in a timed session." },
  { icon: CheckCircle2, title: "Debrief", detail: "Review communication, complexity, and follow-up questions." },
];

export default function InterviewsPage() {
  return (
    <div className="page-stack">
      <PageHeader
        description="A structured rehearsal space for the moments that matter after the algorithm is learned."
        eyebrow="Interview studio"
        title="Practice how you will perform."
        action={<Link className="button button-primary" to="/problems"><span>Start with a problem</span><ArrowRight size={16} /></Link>}
      />
      <section className="interview-banner">
        <div className="interview-banner-art"><Mic2 size={30} /></div>
        <div>
          <StatusPill tone="violet">Foundation workflow</StatusPill>
          <h3>Turn solved problems into calm answers.</h3>
          <p>Interview state, session persistence, and evaluation will build on the same problem, progress, and submission models.</p>
        </div>
        <div className="interview-banner-meta"><Clock3 size={16} /><span>Session model ready for implementation</span></div>
      </section>
      <SectionCard description="The future session will use these explicit stages." title="Interview loop">
        <div className="stage-list">
          {interviewStages.map((stage, index) => {
            const Icon = stage.icon;
            return (
              <div className="stage-row" key={stage.title}>
                <span className="stage-number">0{index + 1}</span>
                <div className="stage-icon"><Icon size={17} /></div>
                <div><strong>{stage.title}</strong><p>{stage.detail}</p></div>
                <ArrowRight size={16} />
              </div>
            );
          })}
        </div>
      </SectionCard>
    </div>
  );
}
