// frontend/app/page.tsx
"use client";

import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { PulseMonitor } from "@/components/PulseMonitor";
import { Card, MetricStat, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

export default function OverviewPage() {
  const healthz = usePolling(() => api.healthz(), 5000);
  const metadata = usePolling(() => api.metadata(), 30000);
  const stats = usePolling(() => api.stats(), 5000);
  const recentActions = usePolling(() => api.recentActions(5), 5000);

  const status = healthz.data?.status ?? (healthz.error ? "down" : "degraded");

  return (
    <div className="flex flex-col gap-6">
      {/* Live ops header */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-6">
          <PulseMonitor status={status} label="Bot status" />
          {healthz.data && (
            <div className="flex gap-8">
              <MetricStat label="Uptime" value={`${Math.floor(healthz.data.uptime_seconds / 60)}m`} />
              <MetricStat
                label="Mongo"
                value={healthz.data.mongo_connected ? "connected" : "down"}
                tone={healthz.data.mongo_connected ? "success" : "danger"}
              />
              <MetricStat
                label="Redis"
                value={healthz.data.redis_connected ? "connected" : "down"}
                tone={healthz.data.redis_connected ? "success" : "danger"}
              />
            </div>
          )}
          {metadata.data && (
            <div className="flex flex-col text-right">
              <span className="text-sm font-medium text-nexora-text-bright">{metadata.data.team_name}</span>
              <span className="text-xs text-nexora-muted font-mono">{metadata.data.model}</span>
            </div>
          )}
        </div>
        {healthz.error && (
          <p className="text-xs text-nexora-danger font-mono mt-3">{healthz.error}</p>
        )}
      </Card>

      {/* Context counts */}
      <Card title="Contexts loaded">
        {healthz.loading && !healthz.data ? (
          <div className="grid grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}
          </div>
        ) : healthz.data ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            <MetricStat label="Categories" value={healthz.data.contexts_loaded.category} />
            <MetricStat label="Merchants" value={healthz.data.contexts_loaded.merchant} />
            <MetricStat label="Customers" value={healthz.data.contexts_loaded.customer} />
            <MetricStat label="Triggers" value={healthz.data.contexts_loaded.trigger} />
          </div>
        ) : (
          <ErrorState message={healthz.error ?? "Unknown error"} />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Actions by trigger template */}
        <Card title="Actions by template (last 200)">
          {stats.data && Object.keys(stats.data.actions_by_template).length > 0 ? (
            <div className="flex flex-col gap-2">
              {Object.entries(stats.data.actions_by_template)
                .sort((a, b) => b[1] - a[1])
                .map(([name, count]) => {
                  const max = Math.max(...Object.values(stats.data!.actions_by_template));
                  const pct = max > 0 ? (count / max) * 100 : 0;
                  return (
                    <div key={name} className="flex items-center gap-3">
                      <span className="text-xs font-mono text-nexora-muted w-44 truncate" title={name}>
                        {name}
                      </span>
                      <div className="flex-1 h-2 bg-nexora-surface-raised rounded-full overflow-hidden">
                        <div
                          className="h-full bg-nexora-accent rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-nexora-text-bright w-6 text-right">{count}</span>
                    </div>
                  );
                })}
            </div>
          ) : (
            <EmptyState
              title="No actions logged yet"
              hint="Actions appear here once /v1/tick composes messages for pushed triggers."
            />
          )}
        </Card>

        {/* Actions by CTA */}
        <Card title="Actions by CTA type (last 200)">
          {stats.data && Object.keys(stats.data.actions_by_cta).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.data.actions_by_cta)
                .sort((a, b) => b[1] - a[1])
                .map(([cta, count]) => (
                  <Badge key={cta} tone="accent">
                    {cta} <span className="ml-1.5 text-nexora-text-bright">{count}</span>
                  </Badge>
                ))}
            </div>
          ) : (
            <EmptyState title="No CTA data yet" />
          )}
        </Card>
      </div>

      {/* Last 5 actions */}
      <Card title="Recent actions">
        {recentActions.loading && !recentActions.data ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}
          </div>
        ) : recentActions.data && recentActions.data.actions.length > 0 ? (
          <div className="flex flex-col divide-y divide-nexora-border">
            {recentActions.data.actions.map((a, i) => (
              <div key={`${a.conversation_id}-${i}`} className="py-3 flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge tone="accent">{a.send_as}</Badge>
                    <span className="text-xs font-mono text-nexora-muted truncate">{a.merchant_id}</span>
                  </div>
                  <span className="text-xs text-nexora-muted shrink-0">{timeAgo(a.logged_at)}</span>
                </div>
                <p className="text-sm text-nexora-text line-clamp-2">{a.body}</p>
                <div className="flex items-center gap-2">
                  <Badge>{a.cta}</Badge>
                  <span className="text-xs font-mono text-nexora-muted truncate">{a.trigger_id}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No actions yet"
            hint="Push contexts and run a tick (via the Simulator page or directly against the API) to see live actions here."
          />
        )}
      </Card>
    </div>
  );
}
