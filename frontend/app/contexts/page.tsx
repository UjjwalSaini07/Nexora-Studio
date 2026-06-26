// frontend/app/contexts/page.tsx
"use client";

import { useMemo, useState } from "react";
import { api, type ContextSummary } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, Badge, EmptyState, ErrorState, Skeleton, CodeBlock } from "@/components/ui";

const SCOPES = ["category", "merchant", "customer", "trigger"] as const;

export default function ContextsPage() {
  const [scope, setScope] = useState<string>("merchant");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ContextSummary | null>(null);

  const contextsPoll = usePolling(() => api.listContexts(scope, 300), 6000);

  const filtered = useMemo(() => {
    if (!contextsPoll.data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return contextsPoll.data.contexts;
    return contextsPoll.data.contexts.filter((c) => c.context_id.toLowerCase().includes(q));
  }, [contextsPoll.data, search]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-vera-text-bright">Context inspector</h1>
        <p className="text-sm text-vera-muted mt-1">
          Every context currently loaded in the bot, by scope. Pulls live from /v1/dashboard/contexts.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {SCOPES.map((s) => (
          <button
            key={s}
            onClick={() => {
              setScope(s);
              setSelected(null);
            }}
            className={`px-3 py-1.5 rounded-md text-sm border transition-colors capitalize ${
              scope === s
                ? "border-vera-accent bg-vera-accent/15 text-vera-accent font-medium"
                : "border-vera-border text-vera-muted hover:text-vera-text"
            }`}
          >
            {s}
          </button>
        ))}
        <input
          type="text"
          placeholder="Search by context_id..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto bg-vera-surface border border-vera-border rounded-md px-3 py-1.5 text-sm text-vera-text placeholder:text-vera-muted focus:outline-none focus:border-vera-accent w-64"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title={`${scope} contexts (${filtered.length})`} className="lg:col-span-1">
          {contextsPoll.loading && !contextsPoll.data ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : contextsPoll.error && !contextsPoll.data ? (
            <ErrorState message={contextsPoll.error} />
          ) : filtered.length === 0 ? (
            <EmptyState title="No contexts found" hint={`No ${scope} contexts match your search, or none have been pushed yet.`} />
          ) : (
            <div className="flex flex-col gap-1 max-h-[600px] overflow-y-auto">
              {filtered.map((ctx) => (
                <button
                  key={ctx.context_id}
                  onClick={() => setSelected(ctx)}
                  className={`text-left px-3 py-2 rounded-lg border transition-colors flex items-center justify-between gap-2 ${
                    selected?.context_id === ctx.context_id
                      ? "border-vera-accent bg-vera-accent/10"
                      : "border-transparent hover:bg-vera-surface-raised"
                  }`}
                >
                  <span className="text-xs font-mono text-vera-text truncate">{ctx.context_id}</span>
                  <Badge>v{ctx.version}</Badge>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card
          title={selected ? selected.context_id : "Select a context"}
          className="lg:col-span-2"
          action={selected && <Badge tone="accent">version {selected.version}</Badge>}
        >
          {!selected ? (
            <EmptyState title="No context selected" hint="Choose an item from the list to inspect its full payload." />
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-4 text-xs text-vera-muted">
                <span>
                  Delivered: <span className="font-mono text-vera-text">{selected.delivered_at}</span>
                </span>
                <span>
                  Stored: <span className="font-mono text-vera-text">{selected.stored_at}</span>
                </span>
              </div>
              <CodeBlock>{JSON.stringify(selected.payload, null, 2)}</CodeBlock>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
