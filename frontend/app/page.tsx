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

  const status = stats.data?.bot_status ?? healthz.data?.status ?? (healthz.error ? "down" : "degraded");

  return (
    <div className="flex flex-col gap-6">
      {/* Live ops header */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-6">
          <PulseMonitor status={status} label="Bot status" />
          {stats.data ? (
            <div className="flex flex-wrap gap-8">
              <MetricStat
                label="Mongo"
                value={stats.data.mongo_connected ? "connected" : "down"}
                tone={stats.data.mongo_connected ? "success" : "danger"}
              />
              <MetricStat
                label="Redis"
                value={stats.data.redis_connected ? "connected" : "down"}
                tone={stats.data.redis_connected ? "success" : "danger"}
              />
              <MetricStat
                label="LLM (Groq)"
                value={stats.data.llm_status}
                tone="success"
              />
            </div>
          ) : healthz.data ? (
            <div className="flex gap-8">
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
          ) : (
            <div className="flex gap-2">
              <Skeleton className="w-20 h-10" />
              <Skeleton className="w-20 h-10" />
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

      {/* Overview Stat Counters */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <Card title="Today's Messages">
          {stats.loading && !stats.data ? (
            <Skeleton className="h-10 w-20" />
          ) : stats.data ? (
            <div className="text-2xl font-semibold text-nexora-text-bright font-mono">
              {stats.data.today_messages}
            </div>
          ) : (
            <span className="text-sm text-nexora-muted">N/A</span>
          )}
        </Card>
        <Card title="Active Conversations">
          {stats.loading && !stats.data ? (
            <Skeleton className="h-10 w-20" />
          ) : stats.data ? (
            <div className="text-2xl font-semibold text-indigo-400 font-mono">
              {stats.data.active_conversations}
            </div>
          ) : (
            <span className="text-sm text-nexora-muted">N/A</span>
          )}
        </Card>
        <Card title="Pending Replies">
          {stats.loading && !stats.data ? (
            <Skeleton className="h-10 w-20" />
          ) : stats.data ? (
            <div className="text-2xl font-semibold text-amber-400 font-mono">
              {stats.data.pending_replies}
            </div>
          ) : (
            <span className="text-sm text-nexora-muted">N/A</span>
          )}
        </Card>
        <Card title="Suppressed Messages">
          {stats.loading && !stats.data ? (
            <Skeleton className="h-10 w-20" />
          ) : stats.data ? (
            <div className="text-2xl font-semibold text-rose-400 font-mono">
              {stats.data.suppressed_messages}
            </div>
          ) : (
            <span className="text-sm text-nexora-muted">N/A</span>
          )}
        </Card>
      </div>

      {/* Decision Quality & Efficiency Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <Card title="Decision Confidence">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-semibold text-emerald-400 font-mono">
                {Math.round(stats.data.average_decision_confidence * 100)}%
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Average Score</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
        <Card title="Latest Tick Latency">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-semibold text-nexora-text-bright font-mono">
                {stats.data.latest_tick_duration}s
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Tick Processing Duration</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
        <Card title="Average Response Time">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-semibold text-nexora-text-bright font-mono">
                {stats.data.average_response_time}s
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">End-to-End LLM Latency</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
        <Card title="System Errors">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className={`text-2xl font-semibold font-mono ${stats.data.recent_errors > 0 ? "text-nexora-danger" : "text-emerald-400"}`}>
                {stats.data.recent_errors}
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Logged Failures</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
      </div>

      {/* Top Performing Categories/Triggers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Top Trigger Signal">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-base font-semibold text-indigo-400 truncate" title={stats.data.top_trigger}>
                {stats.data.top_trigger}
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Most Active Trigger</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
        <Card title="Top Category Vertical">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-base font-semibold text-indigo-400 capitalize">
                {stats.data.top_category}
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Highest Activity Vertical</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
        <Card title="Top Merchant Client">
          {stats.data ? (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-mono text-indigo-400 truncate" title={stats.data.top_merchant}>
                {stats.data.top_merchant}
              </span>
              <span className="text-[10px] text-nexora-muted uppercase font-semibold">Highest volume partner</span>
            </div>
          ) : (
            <Skeleton className="h-14" />
          )}
        </Card>
      </div>

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
        {/* Actions by Trigger */}
        <Card title="Actions by Trigger Type">
          {stats.data && Object.keys(stats.data.actions_by_trigger).length > 0 ? (
            <div className="flex flex-col gap-3.5">
              {Object.entries(stats.data.actions_by_trigger as Record<string, number>)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([name, count]) => {
                  const max = Math.max(...Object.values(stats.data!.actions_by_trigger as Record<string, number>));
                  const pct = max > 0 ? (count / max) * 100 : 0;
                  return (
                    <div key={name} className="flex items-center gap-3">
                      <span className="text-xs font-mono text-nexora-muted w-44 truncate" title={name}>
                        {name}
                      </span>
                      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-nexora-text-bright w-6 text-right">{count}</span>
                    </div>
                  );
                })}
            </div>
          ) : (
            <EmptyState title="No trigger stats logged yet" />
          )}
        </Card>

        {/* Actions by Category */}
        <Card title="Actions by Merchant Category">
          {stats.data && Object.keys(stats.data.actions_by_category).length > 0 ? (
            <div className="flex flex-col gap-3.5">
              {Object.entries(stats.data.actions_by_category as Record<string, number>)
                .sort((a, b) => b[1] - a[1])
                .map(([name, count]) => {
                  const max = Math.max(...Object.values(stats.data!.actions_by_category as Record<string, number>));
                  const pct = max > 0 ? (count / max) * 100 : 0;
                  return (
                    <div key={name} className="flex items-center gap-3">
                      <span className="text-xs font-mono text-nexora-muted w-44 truncate capitalize" title={name}>
                        {name}
                      </span>
                      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-nexora-text-bright w-6 text-right">{count}</span>
                    </div>
                  );
                })}
            </div>
          ) : (
            <EmptyState title="No category stats logged yet" />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Actions by CTA */}
        <Card title="Call To Action (CTA) Distribution">
          {stats.data && Object.keys(stats.data.cta_distribution).length > 0 ? (
            <div className="flex flex-wrap gap-2.5">
              {Object.entries(stats.data.cta_distribution as Record<string, number>)
                .sort((a, b) => b[1] - a[1])
                .map(([cta, count]) => (
                  <Badge key={cta} tone="accent">
                    {cta.replace(/_/g, " ")} <span className="ml-2.5 text-nexora-text-bright font-mono">{count}</span>
                  </Badge>
                ))}
            </div>
          ) : (
            <EmptyState title="No CTA data logged yet" />
          )}
        </Card>

        {/* Confidence score distribution */}
        <Card title="Decision Confidence Distribution">
          {stats.data ? (
            <div className="flex flex-col gap-3">
              {Object.entries(stats.data.decision_confidence_distribution as Record<string, number>).map(([range, count]) => {
                const max = Math.max(...Object.values(stats.data!.decision_confidence_distribution as Record<string, number>) as number[]);
                const pct = max > 0 ? ((count as number) / max) * 100 : 0;
                return (
                  <div key={range} className="flex items-center gap-3">
                    <span className="text-xs font-mono text-nexora-muted w-20">{range}</span>
                    <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-400 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-nexora-text-bright w-6 text-right">{count as number}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <Skeleton className="h-40" />
          )}
        </Card>
      </div>

      {/* Hourly activity charts */}
      <Card title="24-Hour Operations Activity Log">
        {stats.data ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-end justify-between gap-1.5 h-28 pt-4 px-2 border-b border-white/5 bg-white/1 rounded-lg">
              {stats.data.hourly_activity.map((count: number, hour: number) => {
                const max = Math.max(...stats.data!.hourly_activity);
                const heightPct = max > 0 ? (count / max) * 85 + 5 : 5;
                return (
                  <div key={hour} className="flex-1 flex flex-col items-center group relative h-full justify-end">
                    {/* Tooltip */}
                    <div className="absolute bottom-full mb-1 bg-black/85 border border-white/10 text-[9px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono text-white pointer-events-none z-10">
                      {count} msgs
                    </div>
                    <div
                      className="w-full bg-indigo-500/40 hover:bg-indigo-500 rounded-t transition-all cursor-pointer"
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-[10px] text-nexora-muted font-mono font-semibold uppercase px-1">
              <span>00:00 UTC</span>
              <span>06:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>23:00</span>
            </div>
          </div>
        ) : (
          <Skeleton className="h-36" />
        )}
      </Card>

      {/* Live Timeline */}
      <Card title="Live operations timeline">
        {stats.data && stats.data.live_timeline.length > 0 ? (
          <div className="flex flex-col divide-y divide-white/5 max-h-[500px] overflow-y-auto pr-1">
            {stats.data.live_timeline.map((item: any, i: number) => (
              <div key={`${item.id}-${i}`} className="py-4 flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Badge tone={item.event_type === "decision" ? "success" : "accent"}>
                      {item.event_type}
                    </Badge>
                    <span className="text-[10px] font-mono text-nexora-muted truncate max-w-[200px]" title={item.id}>
                      {item.id}
                    </span>
                  </div>
                  <span className="text-[10px] text-nexora-muted font-mono">{timeAgo(item.timestamp)}</span>
                </div>

                {item.inbound && (
                  <div className="pl-3 border-l-2 border-slate-700 py-0.5 text-xs text-slate-400 italic">
                    Inbound: &quot;{item.inbound}&quot;
                  </div>
                )}

                <p className="text-xs text-nexora-text leading-relaxed font-medium">
                  {item.message}
                </p>

                <div className="flex items-center gap-4 text-[10px] font-mono text-nexora-muted flex-wrap">
                  <span>Merchant: <strong className="text-slate-300 font-semibold">{item.merchant}</strong></span>
                  <span>Trigger: <strong className="text-indigo-400 font-semibold">{item.trigger.replace(/_/g, " ")}</strong></span>
                  <span>Confidence: <strong className="text-emerald-400 font-semibold">{Math.round(item.confidence * 100)}%</strong></span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No timeline logs yet" hint="Operational events will stream here once triggers are processed." />
        )}
      </Card>
    </div>
  );
}
