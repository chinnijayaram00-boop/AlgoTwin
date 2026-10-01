import { ShieldCheck } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import SubmissionDetail from "../features/submissions/SubmissionDetail";
import SubmissionHistory from "../features/submissions/SubmissionHistory";
import { PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useAuth } from "../features/auth/useAuth";

/**
 * The learner's submission history, with a detail pane beside it.
 *
 * The open submission lives in the `?submission=` query parameter rather than in
 * component state, so a particular attempt can be linked to, bookmarked, and
 * survives a reload -- the same convention the problem library uses for its
 * filters.
 *
 * Both panes read the same account-scoped endpoints, so the list and the detail
 * can only ever show this learner's own records.
 */
export default function SubmissionsPage() {
  const { isAuthenticated } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("submission");

  function selectSubmission(submissionId) {
    setSearchParams({ submission: String(submissionId) });
  }

  return (
    <div className="page-stack">
      <PageHeader
        action={<StatusPill tone="success">Judged</StatusPill>}
        description="Every attempt you have submitted, with the verdict the judge gave it."
        eyebrow="Submission history"
        title="Every attempt, and what it scored."
      />

      <section className="next-step-banner">
        <div>
          <span className="eyebrow">What a submission is</span>
          <h3>Every attempt is graded by the judge.</h3>
          <p>
            Submitting runs your code in a sandbox against every test case, the hidden ones included,
            and stores the verdict with the pass count, the runtime, and whatever went wrong. You are
            told whether you passed and how far you got; the hidden cases themselves are never shown.
          </p>
        </div>
        <span className="hero-note">
          <ShieldCheck size={14} /> Only an accepted verdict marks a problem solved
        </span>
      </section>

      <div className="submissions-layout">
        <SectionCard
          description="Scoped to your account. Nobody else can read these rows."
          title="Submission history"
        >
          <SubmissionHistory enabled={isAuthenticated} onSelect={selectSubmission} selectedId={selectedId} />
        </SectionCard>

        <SectionCard description="The source you submitted, exactly as it was graded." title="Submission detail">
          <SubmissionDetail enabled={isAuthenticated} submissionId={selectedId} />
        </SectionCard>
      </div>
    </div>
  );
}
