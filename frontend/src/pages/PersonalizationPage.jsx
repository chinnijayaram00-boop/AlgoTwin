import { Compass, Sparkles } from "lucide-react";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  SectionCard,
} from "../components/ui/Feedback";
import MentorPanel from "../features/personalization/MentorPanel";
import ProfileOverview from "../features/personalization/ProfileOverview";
import RecommendationList from "../features/personalization/RecommendationList";
import SignalsPanel from "../features/personalization/SignalsPanel";
import { formatPercent } from "../features/analytics/analyticsFormat";
import { usePersonalization } from "../features/personalization/usePersonalization";

export default function PersonalizationPage() {
  const { data, error, errorStatus, loading, reload } = usePersonalization();

  return (
    <div className="page-stack">
      <PageHeader
        description="Strengths, weaknesses, and next steps derived from your own recorded work — plus a coach that reasons over the same profile."
        eyebrow="Personalized coach"
        title="See what your work says about you."
      />

      {loading ? <LoadingState label="Building your profile" /> : null}
      {errorStatus === 401 ? (
        <div className="inline-notice" role="alert">
          Sign in again to load your profile. Your session may have expired.
        </div>
      ) : null}
      {error && errorStatus !== 401 ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? <ProfileView profile={data} /> : null}
    </div>
  );
}

function ProfileView({ profile }) {
  return (
    <>
      <ProfileOverview overview={profile.overview} />

      <div className="analytics-grid">
        <SectionCard
          description="Signals the recorded evidence supports. Each one names the measurement it came from."
          title="Strengths"
        >
          <SignalsPanel
            emptyDescription="Solve or attempt a problem and what you are doing well will show up here."
            emptyTitle="No strengths recorded yet"
            signals={profile.strengths}
            tone="violet"
          />
        </SectionCard>

        <SectionCard
          description="Where the record says to put your attention next, in rough priority order."
          title="Worth your attention"
        >
          <SignalsPanel
            emptyDescription="Nothing is standing out yet — keep building the record."
            emptyTitle="Nothing to flag"
            signals={profile.weaknesses}
            tone="medium"
          />
        </SectionCard>
      </div>

      <SectionCard
        description="The next few problems to try, all inside the stage you are standing in."
        title="Suggested next problems"
      >
        <RecommendationList recommendations={profile.recommendations} />
      </SectionCard>

      <SectionCard
        description="Topics ordered weakest-first — the most productive places to spend your next session."
        title="Focus areas"
      >
        {profile.focus_areas.length > 0 ? (
          <div className="focus-areas">
            {profile.focus_areas.map((area) => (
              <div className="focus-area" key={area.topic}>
                <div className="focus-area-top">
                  <strong>{area.topic}</strong>
                  <span>
                    {area.solved}/{area.total} · {formatPercent(area.completion_percentage)}
                  </span>
                </div>
                <div className="snapshot-meter">
                  <span style={{ width: `${area.completion_percentage}%` }} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            description="Topics appear as the catalog gains published problems."
            title="No focus areas yet"
          />
        )}
      </SectionCard>

      <SectionCard
        description="Grounded in the profile above. If no model is available, you still get coaching written from your own record."
        title="Ask the AI coach"
      >
        <MentorPanel />
      </SectionCard>

      <p className="coach-footnote">
        <Compass aria-hidden="true" size={14} /> Every number here reduces to a stored row; nothing is
        estimated and nothing is sampled.
        <Sparkles aria-hidden="true" size={14} />
      </p>
    </>
  );
}
