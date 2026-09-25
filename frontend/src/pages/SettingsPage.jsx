import { Database, KeyRound, Server, ShieldCheck } from "lucide-react";
import { useCallback } from "react";

import { ErrorState, LoadingState, PageHeader, SectionCard, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { platformApi } from "../services/platformService";

export default function SettingsPage() {
  const loadStatus = useCallback(async () => {
    const [health, ai] = await Promise.all([platformApi.health(), platformApi.aiStatus()]);
    return { health, ai };
  }, []);
  const { data, error, loading, reload } = useApiResource(loadStatus);

  return (
    <div className="page-stack">
      <PageHeader
        description="Environment-driven configuration keeps local development simple and deployment explicit."
        eyebrow="Workspace configuration"
        title="Know what is connected."
      />
      {loading ? <LoadingState label="Checking workspace services" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? (
        <div className="settings-grid">
          <SectionCard title="API service" description="Readiness metadata from the FastAPI application.">
            <SettingRow icon={Server} label="Service" value={data.health.service} />
            <SettingRow icon={ShieldCheck} label="Environment" value={data.health.environment} />
            <SettingRow icon={Database} label="API version" value={data.health.version} />
          </SectionCard>
          <SectionCard title="AI boundary" description="The UI never receives or displays provider secrets.">
            <SettingRow icon={KeyRound} label="Provider" value={data.ai.provider} />
            <SettingRow icon={ShieldCheck} label="Configuration" value={data.ai.configured ? "Configured" : "Disabled"} />
            <div className="settings-message"><StatusPill tone={data.ai.configured ? "success" : "neutral"}>{data.ai.configured ? "Ready" : "Not enabled"}</StatusPill><p>{data.ai.message}</p></div>
          </SectionCard>
        </div>
      ) : null}
      <SectionCard title="Configuration contract" description="Use environment variables rather than committing local values.">
        <div className="config-list">
          <div><code>VITE_API_URL</code><span>Frontend API base URL</span></div>
          <div><code>DATABASE_URL</code><span>SQLite locally or PostgreSQL in deployment</span></div>
          <div><code>AI_PROVIDER</code><span>Provider adapter selection</span></div>
          <div><code>AI_API_KEY</code><span>Server-only provider credential</span></div>
        </div>
      </SectionCard>
    </div>
  );
}

function SettingRow({ icon: Icon, label, value }) {
  return (
    <div className="setting-row"><Icon size={17} /><span>{label}</span><strong>{value}</strong></div>
  );
}
