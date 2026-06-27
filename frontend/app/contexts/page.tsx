// frontend/app/contexts/page.tsx
"use client";

import { useMemo, useState, useEffect } from "react";
import { api, type ContextSummary } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

const SCOPES = ["category", "merchant", "customer", "trigger"] as const;

function computeLineDiff(oldStr: string, newStr: string) {
  const oldLines = oldStr.split("\n");
  const newLines = newStr.split("\n");
  const diff: Array<{ type: "add" | "delete" | "same"; text: string }> = [];
  
  let i = 0, j = 0;
  while (i < oldLines.length || j < newLines.length) {
    if (i < oldLines.length && j < newLines.length && oldLines[i] === newLines[j]) {
      diff.push({ type: "same", text: oldLines[i] });
      i++;
      j++;
    } else if (j < newLines.length && (i >= oldLines.length || !oldLines.slice(i).includes(newLines[j]))) {
      diff.push({ type: "add", text: newLines[j] });
      j++;
    } else {
      diff.push({ type: "delete", text: oldLines[i] });
      i++;
    }
  }
  return diff;
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

export default function ContextsPage() {
  const [scope, setScope] = useState<string>("merchant");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ContextSummary | null>(null);
  
  // History and diff states
  const [history, setHistory] = useState<ContextSummary[]>([]);
  const [compareVersion, setCompareVersion] = useState<number | null>(null);
  const [diffMode, setDiffMode] = useState(false);
  
  // JSON viewer states
  const [jsonSearch, setJsonSearch] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  const contextsPoll = usePolling(() => api.listContexts(scope, 300), 6000, [scope]);

  const filtered = useMemo(() => {
    if (!contextsPoll.data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return contextsPoll.data.contexts;
    return contextsPoll.data.contexts.filter((c) => c.context_id.toLowerCase().includes(q));
  }, [contextsPoll.data, search]);

  // Fetch history when selected context changes
  useEffect(() => {
    if (selected) {
      api.getContextHistory(selected.scope, selected.context_id)
        .then(res => {
          setHistory(res.history);
          setCompareVersion(null);
          setDiffMode(false);
        })
        .catch(err => console.error("Error fetching context history:", err));
    } else {
      setHistory([]);
      setCompareVersion(null);
      setDiffMode(false);
    }
    setJsonSearch("");
  }, [selected]);

  // Copy to clipboard
  const handleCopy = () => {
    if (!selected) return;
    navigator.clipboard.writeText(JSON.stringify(selected.payload, null, 2))
      .then(() => {
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      });
  };

  const selectedJsonString = selected ? JSON.stringify(selected.payload, null, 2) : "";
  
  // Compute diff against selected version
  const diffLines = useMemo(() => {
    if (!selected || compareVersion === null) return [];
    const oldVersionDoc = history.find(h => h.version === compareVersion);
    if (!oldVersionDoc) return [];
    const oldStr = JSON.stringify(oldVersionDoc.payload, null, 2);
    const newStr = JSON.stringify(selected.payload, null, 2);
    return computeLineDiff(oldStr, newStr);
  }, [selected, compareVersion, history]);

  // Highlight matches inside JSON lines
  const renderJsonLine = (line: string, index: number) => {
    const q = jsonSearch.trim().toLowerCase();
    if (!q || !line.toLowerCase().includes(q)) {
      return <div key={index} className="hover:bg-white/2 px-2 py-0.5">{line}</div>;
    }

    const parts = [];
    let remaining = line;
    let idx = remaining.toLowerCase().indexOf(q);

    while (idx !== -1) {
      parts.push(remaining.substring(0, idx));
      parts.push(
        <mark key={idx} className="bg-yellow-500/30 text-yellow-200 px-0.5 rounded border border-yellow-500/25">
          {remaining.substring(idx, idx + q.length)}
        </mark>
      );
      remaining = remaining.substring(idx + q.length);
      idx = remaining.toLowerCase().indexOf(q);
    }
    parts.push(remaining);

    return (
      <div key={index} className="bg-yellow-500/5 hover:bg-yellow-500/10 px-2 py-0.5">
        {parts}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-nexora-text-bright">Internal Context Registry</h1>
        <p className="text-sm text-nexora-muted mt-1">
          Durable state record profiles loaded across categories, merchants, customers, and active triggers.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {SCOPES.map((s) => (
            <button
              key={s}
              onClick={() => {
                setScope(s);
                setSelected(null);
              }}
              className={`px-4 py-1.5 rounded-lg text-sm border transition-all duration-200 capitalize font-semibold ${
                scope === s
                  ? "border-indigo-500/30 bg-indigo-500/10 text-indigo-400 shadow-[0_0_12px_rgba(99,102,241,0.12)]"
                  : "border-white/5 bg-white/3 text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter context ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto glass-input px-3.5 py-1.5 text-sm placeholder:text-slate-500 focus:outline-none w-64"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Context Sidebar List */}
        <Card title={`${scope} contexts (${filtered.length})`} className="lg:col-span-1">
          {contextsPoll.loading && !contextsPoll.data ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : contextsPoll.error && !contextsPoll.data ? (
            <ErrorState message={contextsPoll.error} />
          ) : filtered.length === 0 ? (
            <EmptyState title="No contexts found" hint={`No ${scope} contexts match your search.`} />
          ) : (
            <div className="flex flex-col gap-1 max-h-[600px] overflow-y-auto pr-1">
              {filtered.map((ctx) => {
                const isSel = selected?.context_id === ctx.context_id;
                return (
                  <button
                    key={ctx.context_id}
                    onClick={() => setSelected(ctx)}
                    className={`text-left px-3.5 py-2.5 rounded-lg border transition-all duration-200 flex items-center justify-between gap-2 ${
                      isSel
                        ? "border-indigo-500/25 bg-indigo-500/10 shadow-[0_0_12px_rgba(99,102,241,0.06)]"
                        : "border-transparent bg-white/2 hover:bg-white/5"
                    }`}
                  >
                    <span className="text-xs font-mono text-white truncate">{ctx.context_id}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Badge>v{ctx.version}</Badge>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Card>

        {/* Selected Context Detail Viewer */}
        <Card
          title={selected ? selected.context_id : "Select a context"}
          className="lg:col-span-2"
          action={selected && <Badge tone="accent">version {selected.version}</Badge>}
        >
          {!selected ? (
            <EmptyState title="No context selected" hint="Choose a context from the list to audit its JSON payload." />
          ) : (
            <div className="flex flex-col gap-4">
              {/* Metadata details and freshness */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3.5 rounded-xl border border-white/5 bg-white/1 font-mono text-xs text-slate-300">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Delivered At</span>
                  <span className="truncate">{selected.delivered_at}</span>
                  <span className="text-[9px] text-indigo-400 font-semibold">({relativeTime(selected.delivered_at)})</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Stored At</span>
                  <span className="truncate">{selected.stored_at}</span>
                  <span className="text-[9px] text-indigo-400 font-semibold">({relativeTime(selected.stored_at)})</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Status / Freshness</span>
                  <span className="text-emerald-400 font-semibold">● Fresh State</span>
                  <span className="text-[9px] text-slate-400">Pushed to Mongo</span>
                </div>
              </div>

              {/* Version History Selector & Diff Toggles */}
              {history.length > 1 && (
                <div className="flex flex-wrap items-center gap-3 border border-white/5 bg-white/2 p-3 rounded-xl">
                  <span className="text-xs font-semibold text-slate-300">Payload Versions:</span>
                  <div className="flex items-center gap-2">
                    <select
                      value={compareVersion ?? ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCompareVersion(val ? Number(val) : null);
                        setDiffMode(!!val);
                      }}
                      className="bg-black/60 border border-white/10 text-xs text-white rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="">(Compare with version...)</option>
                      {history
                        .filter(h => h.version !== selected.version)
                        .map(h => (
                          <option key={h.version} value={h.version}>v{h.version} ({relativeTime(h.delivered_at)})</option>
                        ))}
                    </select>
                  </div>
                  {diffMode && (
                    <Badge tone="danger">Diff Mode Active</Badge>
                  )}
                </div>
              )}

              {/* Actions Toolbar */}
              <div className="flex items-center justify-between gap-3 border-b border-white/5 pb-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    className="px-3 py-1.5 rounded-lg border border-white/5 bg-white/2 hover:bg-white/5 text-xs font-semibold text-slate-300 transition-all flex items-center gap-1.5"
                  >
                    {copySuccess ? "Copied! ✓" : "Copy Payload"}
                  </button>
                  <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="px-3 py-1.5 rounded-lg border border-white/5 bg-white/2 hover:bg-white/5 text-xs font-semibold text-slate-300 transition-all"
                  >
                    {isCollapsed ? "Expand View" : "Collapse View"}
                  </button>
                </div>
                {!diffMode && (
                  <input
                    type="text"
                    placeholder="Search text in JSON..."
                    value={jsonSearch}
                    onChange={(e) => setJsonSearch(e.target.value)}
                    className="glass-input px-3 py-1.5 text-xs placeholder:text-slate-500 focus:outline-none w-56 font-mono"
                  />
                )}
              </div>

              {/* Code viewer / Diff content */}
              {!isCollapsed && (
                <div className="font-mono text-xs bg-black/60 border border-white/5 rounded-xl p-4.5 max-h-[500px] overflow-y-auto flex flex-col backdrop-blur-sm shadow-inner leading-relaxed select-text">
                  {diffMode ? (
                    diffLines.map((line, idx) => {
                      let color = "text-nexora-text opacity-95";
                      let prefix = "  ";
                      if (line.type === "add") {
                        color = "text-emerald-400 bg-emerald-500/10 font-bold border-l-2 border-emerald-500 pl-1.5";
                        prefix = "+ ";
                      } else if (line.type === "delete") {
                        color = "text-rose-400 bg-rose-500/10 line-through opacity-70 border-l-2 border-rose-500 pl-1.5";
                        prefix = "- ";
                      }
                      return (
                        <div key={idx} className={`px-2 py-0.5 rounded ${color}`}>
                          {prefix}{line.text}
                        </div>
                      );
                    })
                  ) : (
                    selectedJsonString.split("\n").map(renderJsonLine)
                  )}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
