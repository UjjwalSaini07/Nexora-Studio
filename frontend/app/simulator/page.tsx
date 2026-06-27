// frontend/app/simulator/page.tsx
"use client";

import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Card, Badge, EmptyState, MetricStat } from "@/components/ui";

interface LogLine {
  id: number;
  text: string;
  tone: "default" | "success" | "warn" | "danger";
}

type RunState = "idle" | "running" | "done" | "error";

/**
 * A browser-driven simulator runner. It does NOT reimplement judge scoring
 * (that requires magicpin's own LLM judge — see challenge-testing-brief.md
 * and judge_simulator.py for the real thing) — it drives the bot through
 * the same operational sequence the harness uses (healthz check, context
 * warmup, tick triggers) against whatever dataset the user points it at,
 * and streams the results live so you can sanity-check the bot end-to-end
 * without leaving the dashboard.
 *
 * For full LLM-judged scoring, run judge_simulator.py directly — this page
 * complements that, it doesn't replace it.
 */
export default function SimulatorPage() {
  const [runState, setRunState] = useState<RunState>("idle");
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [triggerIds, setTriggerIds] = useState("");
  const [nowIso, setNowIso] = useState(() => new Date().toISOString());
  const [summary, setSummary] = useState<{ pushed: number; actions: number; errors: number } | null>(null);
  const logIdRef = useRef(0);

  const appendLog = useCallback((text: string, tone: LogLine["tone"] = "default") => {
    logIdRef.current += 1;
    setLogs((prev) => [...prev, { id: logIdRef.current, text, tone }]);
  }, []);

  const runHealthCheck = useCallback(async () => {
    setRunState("running");
    setLogs([]);
    setSummary(null);
    appendLog(`Connecting to bot at ${api.botUrl} ...`);
    try {
      const health = await api.healthz();
      appendLog(`healthz -> status=${health.status}, uptime=${health.uptime_seconds}s`, health.status === "ok" ? "success" : "warn");
      appendLog(
        `contexts_loaded: category=${health.contexts_loaded.category} merchant=${health.contexts_loaded.merchant} customer=${health.contexts_loaded.customer} trigger=${health.contexts_loaded.trigger}`
      );
      const meta = await api.metadata();
      appendLog(`metadata -> team="${meta.team_name}" model="${meta.model}"`, "success");
      setRunState("done");
    } catch (err) {
      appendLog(`ERROR: ${err instanceof Error ? err.message : "unknown error"}`, "danger");
      setRunState("error");
    }
  }, [appendLog]);

  const runTick = useCallback(async () => {
    const ids = triggerIds
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    if (ids.length === 0) {
      appendLog("No trigger IDs provided — enter at least one (comma or newline separated).", "warn");
      return;
    }

    setRunState("running");
    setLogs([]);
    setSummary(null);
    appendLog(`Running /v1/tick with now=${nowIso} for ${ids.length} trigger(s)...`);

    let actionCount = 0;
    let errorCount = 0;
    try {
      const result = await api.tick(nowIso, ids);
      actionCount = result.actions.length;
      appendLog(`tick complete -> ${result.actions.length} action(s) returned`, result.actions.length > 0 ? "success" : "warn");
      for (const action of result.actions) {
        appendLog(`  [${action.trigger_id}] send_as=${action.send_as} cta=${action.cta}`, "default");
        appendLog(`    "${action.body}"`, "default");
        appendLog(`    rationale: ${action.rationale}`, "default");
      }
      const missing = ids.filter((id) => !result.actions.some((a) => a.trigger_id === id));
      for (const id of missing) {
        appendLog(`  [${id}] no action returned (suppressed, expired, missing context, or LLM declined)`, "warn");
      }
      setRunState("done");
    } catch (err) {
      errorCount = 1;
      appendLog(`ERROR: ${err instanceof Error ? err.message : "unknown error"}`, "danger");
      setRunState("error");
    }

    setSummary({ pushed: ids.length, actions: actionCount, errors: errorCount });
  }, [triggerIds, nowIso, appendLog]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-nexora-text-bright">Simulator</h1>
        <p className="text-sm text-nexora-muted mt-1">
          Drive the real bot through health checks and tick triggers, with live output below. For full
          5-dimension LLM-judged scoring, run{" "}
          <code className="font-mono text-nexora-text">judge_simulator.py</code> directly with your own
          provider key.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Health check">
          <p className="text-sm text-nexora-muted mb-4">
            Checks <code className="font-mono">/v1/healthz</code> and{" "}
            <code className="font-mono">/v1/metadata</code> against{" "}
            <span className="font-mono text-nexora-text">{api.botUrl}</span>.
          </p>
          <button
            onClick={runHealthCheck}
            disabled={runState === "running"}
            className="px-4 py-2 rounded-md bg-nexora-accent text-white text-sm font-medium hover:bg-nexora-accent-soft transition-colors disabled:opacity-50"
          >
            {runState === "running" ? "Running..." : "Run health check"}
          </button>
        </Card>

        <Card title="Tick triggers">
          <label className="text-xs uppercase tracking-wider text-nexora-muted">Trigger IDs (comma or newline separated)</label>
          <textarea
            value={triggerIds}
            onChange={(e) => setTriggerIds(e.target.value)}
            placeholder="trg_001_research_digest_dentists, trg_004_recall_due_dentists"
            rows={3}
            className="mt-2 w-full bg-nexora-bg border border-nexora-border rounded-md px-3 py-2 text-sm font-mono text-nexora-text placeholder:text-nexora-muted focus:outline-none focus:border-nexora-accent resize-none"
          />
          <label className="text-xs uppercase tracking-wider text-nexora-muted mt-3 block">Simulated &quot;now&quot; (ISO 8601)</label>
          <input
            type="text"
            value={nowIso}
            onChange={(e) => setNowIso(e.target.value)}
            className="mt-2 w-full bg-nexora-bg border border-nexora-border rounded-md px-3 py-2 text-sm font-mono text-nexora-text focus:outline-none focus:border-nexora-accent"
          />
          <button
            onClick={runTick}
            disabled={runState === "running"}
            className="mt-3 px-4 py-2 rounded-md bg-nexora-accent text-white text-sm font-medium hover:bg-nexora-accent-soft transition-colors disabled:opacity-50"
          >
            {runState === "running" ? "Running..." : "Run tick"}
          </button>
        </Card>
      </div>

      {summary && (
        <Card title="Run summary">
          <div className="grid grid-cols-3 gap-6">
            <MetricStat label="Triggers requested" value={summary.pushed} />
            <MetricStat
              label="Actions returned"
              value={summary.actions}
              tone={summary.actions > 0 ? "success" : "warn"}
            />
            <MetricStat label="Errors" value={summary.errors} tone={summary.errors > 0 ? "danger" : "success"} />
          </div>
        </Card>
      )}

      <Card title="Live output">
        {logs.length === 0 ? (
          <EmptyState title="No run yet" hint="Run a health check or tick above to see live output here." />
        ) : (
          <div className="font-mono text-xs bg-nexora-bg border border-nexora-border rounded-lg p-4 max-h-[400px] overflow-y-auto flex flex-col gap-1">
            {logs.map((line) => (
              <div
                key={line.id}
                className={
                  line.tone === "success"
                    ? "text-nexora-success"
                    : line.tone === "warn"
                    ? "text-nexora-warn"
                    : line.tone === "danger"
                    ? "text-nexora-danger"
                    : "text-nexora-text"
                }
              >
                {line.text}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Connector status" className="opacity-90">
        <div className="flex items-center gap-2">
          <Badge tone="accent">bot url</Badge>
          <span className="text-sm font-mono text-nexora-text">{api.botUrl}</span>
        </div>
        <p className="text-xs text-nexora-muted mt-2">
          Set <code className="font-mono">NEXT_PUBLIC_BOT_URL</code> in your frontend{" "}
          <code className="font-mono">.env</code> to point this dashboard at a different backend.
        </p>
      </Card>
    </div>
  );
}
