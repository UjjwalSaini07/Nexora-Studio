// frontend/app/simulator/page.tsx
"use client";

import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Card, Badge, EmptyState, MetricStat } from "@/components/ui";

interface TriggerRank {
  trigger_id: string;
  urgency: number;
  kind: string;
  priority_score?: number;
  priority_rank?: number;
  priority_reason?: string;
  payload: any;
}

interface SimulatedAction {
  conversation_id: string;
  merchant_id: string | null;
  customer_id: string | null;
  send_as: string;
  trigger_id: string;
  template_name: string;
  body: string;
  cta: string;
  suppression_key: string;
  rationale: string;
  confidence: number;
  latency: number;
  token_usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  actions_logged: boolean;
}

interface RejectedTrigger {
  trigger_id: string;
  reason: string;
  suppression_key?: string;
}

type RunState = "idle" | "running" | "done" | "error";

export default function SimulatorPage() {
  const [runState, setRunState] = useState<RunState>("idle");
  const [nowIso, setNowIso] = useState(() => "2026-04-26T10:35:00Z");
  const [triggerIds, setTriggerIds] = useState("trg_001_research_digest_dentists, trg_003_recall_due_priya, trg_004_perf_dip_bharat, trg_013_corporate_thali_planning");
  
  // Simulation states
  const [statusMessage, setStatusMessage] = useState("");
  const [activeTrigger, setActiveTrigger] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<{ name: string; status: string } | null>(null);
  
  const [ranking, setRanking] = useState<TriggerRank[]>([]);
  const [actions, setActions] = useState<SimulatedAction[]>([]);
  const [rejected, setRejected] = useState<RejectedTrigger[]>([]);
  const [summary, setSummary] = useState<{ requested: number; accepted: number; rejected: number } | null>(null);

  const runSimulation = useCallback(async () => {
    const ids = triggerIds
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    if (ids.length === 0) {
      setStatusMessage("Enter at least one trigger ID.");
      return;
    }

    setRunState("running");
    setStatusMessage("Initializing simulation session...");
    setActiveTrigger(null);
    setActiveStage(null);
    setRanking([]);
    setActions([]);
    setRejected([]);
    setSummary(null);

    try {
      const url = `${api.botUrl}/v1/dashboard/simulate_tick_stream?now=${encodeURIComponent(nowIso)}&trigger_ids=${encodeURIComponent(ids.join(","))}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to initialize stream: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("ReadableStream is not supported by the browser.");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const rawData = line.substring(6).trim();
            if (!rawData) continue;
            try {
              const data = JSON.parse(rawData);
              
              if (data.event === "start") {
                setStatusMessage(data.message);
              } else if (data.event === "signal_ranking") {
                setRanking(data.ranking);
                setStatusMessage("Signal Ranking stage complete. Processing triggers by urgency...");
              } else if (data.event === "trigger_start") {
                setActiveTrigger(data.trigger_id);
                setActiveStage(null);
              } else if (data.event === "stage") {
                setActiveStage({ name: data.stage, status: data.status });
              } else if (data.event === "action") {
                const simulated: SimulatedAction = {
                  ...data.action,
                  actions_logged: data.actions_logged,
                  confidence: data.confidence,
                  latency: data.latency,
                  token_usage: data.token_usage
                };
                setActions((prev) => [...prev, simulated]);
              } else if (data.event === "trigger_skipped") {
                setRejected((prev) => [
                  ...prev,
                  { trigger_id: data.trigger_id, reason: data.reason, suppression_key: data.suppression_key }
                ]);
              } else if (data.event === "done") {
                setSummary({
                  requested: ids.length,
                  accepted: data.actions_returned,
                  rejected: ids.length - data.actions_returned
                });
                setStatusMessage("Simulation finished successfully.");
                setRunState("done");
              }
            } catch (e) {
              console.error("Error parsing stream line:", e, rawData);
            }
          }
        }
      }
    } catch (err) {
      setStatusMessage(`ERROR: ${err instanceof Error ? err.message : "Stream processing failed"}`);
      setRunState("error");
    }
  }, [triggerIds, nowIso]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-nexora-text-bright">Operations Simulation Center</h1>
        <p className="text-sm text-nexora-muted mt-1">
          Perform dry-runs and inspect the complete multi-stage reasoning pipeline (Signal Ranking, Decision Engine, Composer, Validator, Reviewer) in real time.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Simulator controls */}
        <Card title="Tick Simulator Controls" className="lg:col-span-1">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs uppercase tracking-wider text-slate-400 font-medium font-mono">Trigger IDs (comma separated)</label>
              <textarea
                value={triggerIds}
                onChange={(e) => setTriggerIds(e.target.value)}
                placeholder="trg_001_research_digest_dentists, trg_003_recall_due_priya..."
                rows={4}
                className="w-full glass-input px-3.5 py-2.5 text-xs font-mono placeholder:text-slate-500 focus:outline-none resize-none"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs uppercase tracking-wider text-slate-400 font-medium font-mono">Simulated &quot;now&quot; (ISO 8601)</label>
              <input
                type="text"
                value={nowIso}
                onChange={(e) => setNowIso(e.target.value)}
                className="w-full glass-input px-3.5 py-2 text-xs font-mono focus:outline-none"
              />
            </div>

            <button
              onClick={runSimulation}
              disabled={runState === "running"}
              className="px-5 py-2.5 rounded-lg glass-button-primary text-sm font-semibold transition-all disabled:opacity-50 disabled:transform-none"
            >
              {runState === "running" ? "Simulating..." : "Run Tick Simulation"}
            </button>

            {statusMessage && (
              <div className="mt-2 text-xs font-mono border border-white/5 bg-black/40 rounded-lg p-3 text-indigo-400 animate-pulse">
                {statusMessage}
              </div>
            )}
          </div>
        </Card>

        {/* Live reasoning pipeline stream */}
        <Card title="Reasoning Pipeline Audit" className="lg:col-span-2">
          {runState === "idle" ? (
            <EmptyState title="Idle" hint="Input triggers and run simulation to inspect the reasoning stages." />
          ) : (
            <div className="flex flex-col gap-4">
              {/* Active processing element */}
              {runState === "running" && activeTrigger && (
                <div className="flex flex-col gap-2.5 p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5 animate-pulse">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-mono text-white">Active Trigger: <strong className="text-indigo-400 font-semibold">{activeTrigger}</strong></span>
                    <Badge tone="accent">Processing</Badge>
                  </div>
                  {activeStage && (
                    <div className="flex flex-col gap-1 pl-3 border-l-2 border-indigo-500">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">{activeStage.name} Stage</span>
                      <p className="text-xs text-slate-300 italic">{activeStage.status}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Signal Ranking display */}
              {ranking.length > 0 && (
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-semibold text-slate-400 font-mono">1. Signal Ranking (Priority Engine — multi-factor score)</span>
                  <div className="flex flex-col gap-1.5">
                    {ranking.map((r, i) => (
                      <div key={r.trigger_id} className={`flex flex-col gap-0.5 px-3 py-2 rounded-lg border ${r.urgency >= 4 ? "border-rose-500/30 bg-rose-500/5" : "border-white/5 bg-white/2"}`}>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded ${r.urgency >= 4 ? "bg-rose-500/20 text-rose-400" : "bg-indigo-500/20 text-indigo-400"}`}>
                            #{r.priority_rank ?? i + 1}
                          </span>
                          <span className="text-xs font-mono text-white truncate max-w-[220px]" title={r.trigger_id}>{r.trigger_id}</span>
                          <span className="ml-auto text-[10px] font-bold text-emerald-400 font-mono bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full">
                            {r.priority_score ?? "–"} pts
                          </span>
                        </div>
                        <div className="flex items-center gap-2 pl-6">
                          <span className="text-[9px] font-mono text-slate-500">u:{r.urgency} · {r.kind}</span>
                          {r.priority_reason && (
                            <span className="text-[9px] text-slate-600 italic truncate max-w-[280px]" title={r.priority_reason}>
                              {r.priority_reason.replace("score=" + (r.priority_score ?? ""), "").replace(": ", "").trim().slice(0, 80)}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary stats */}
              {summary && (
                <div className="grid grid-cols-3 gap-4 border border-white/5 bg-white/2 p-4 rounded-xl">
                  <MetricStat label="Total Requested" value={summary.requested} />
                  <MetricStat label="Actions Returned" value={summary.accepted} tone="success" />
                  <MetricStat label="Rejected/Skipped" value={summary.rejected} tone="warn" />
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Composed actions results table */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left 2 cols: Composed Actions */}
        <Card title={`Composed Actions List (${actions.length})`} className="xl:col-span-2">
          {actions.length === 0 ? (
            <EmptyState title="No actions composed yet" hint="Composed messages will stream here in real time." />
          ) : (
            <div className="flex flex-col divide-y divide-white/5">
              {actions.map((act, i) => (
                <div key={`${act.trigger_id}-${i}`} className="py-4.5 flex flex-col gap-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Badge tone="success">Selected: {act.trigger_id}</Badge>
                      <Badge>{act.send_as}</Badge>
                      <Badge tone="accent">{act.cta}</Badge>
                    </div>
                    <span className="text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                      {Math.round(act.confidence * 100)}% Confidence
                    </span>
                  </div>

                  <p className="text-sm font-semibold text-white leading-relaxed bg-white/2 p-3.5 rounded-xl border border-white/5">
                    {act.body}
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-slate-300">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[9px] uppercase tracking-wider text-slate-500">Rationale</span>
                      <span className="italic text-slate-400">{act.rationale}</span>
                    </div>
                    <div className="flex flex-col gap-1 bg-black/40 border border-white/5 rounded-lg p-2 text-[10px]">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Latency:</span>
                        <span className="text-indigo-400 font-semibold">{act.latency}s</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">LLM Tokens:</span>
                        <span>{act.token_usage.prompt_tokens}p + {act.token_usage.completion_tokens}c = {act.token_usage.total_tokens}t</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">DB Sync:</span>
                        <span className={act.actions_logged ? "text-emerald-400" : "text-rose-400"}>
                          {act.actions_logged ? "Logged to Mongo" : "Sync Failed"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Right 1 col: Rejected Triggers */}
        <Card title={`Rejected Triggers (${rejected.length})`} className="xl:col-span-1">
          {rejected.length === 0 ? (
            <EmptyState title="No rejections" hint="Triggers skipped due to suppressions or expiry will appear here." />
          ) : (
            <div className="flex flex-col gap-3">
              {rejected.map((rej, i) => (
                <div key={`${rej.trigger_id}-${i}`} className="p-3 border border-white/5 bg-white/1 rounded-xl flex flex-col gap-1.5 font-mono text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-rose-400 truncate max-w-[180px]" title={rej.trigger_id}>
                      {rej.trigger_id}
                    </span>
                    <Badge tone="warn">Skipped</Badge>
                  </div>
                  <div className="text-[10px] text-slate-400">
                    <span className="text-slate-500 uppercase tracking-wider block text-[8px] font-semibold">Reason</span>
                    <p className="mt-0.5">{rej.reason}</p>
                  </div>
                  {rej.suppression_key && (
                    <div className="text-[9px] text-slate-500 truncate" title={rej.suppression_key}>
                      key: {rej.suppression_key}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
