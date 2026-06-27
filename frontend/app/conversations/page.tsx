// frontend/app/conversations/page.tsx
"use client";

import { useState } from "react";
import { api, type ReplyLogEntry } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

function actionTone(action: string): "success" | "warn" | "danger" | "default" {
  if (action === "send") return "success";
  if (action === "wait") return "warn";
  if (action === "end") return "danger";
  return "default";
}

function groupByConversation(replies: ReplyLogEntry[]): Map<string, ReplyLogEntry[]> {
  const map = new Map<string, ReplyLogEntry[]>();
  for (const r of replies) {
    const existing = map.get(r.conversation_id) ?? [];
    existing.push(r);
    map.set(r.conversation_id, existing);
  }
  // newest activity first within each conversation, but keep conversations
  // themselves ordered by their most recent reply
  for (const [, list] of map) {
    list.sort((a, b) => new Date(a.logged_at).getTime() - new Date(b.logged_at).getTime());
  }
  return map;
}

export default function ConversationsPage() {
  const repliesPoll = usePolling(() => api.recentReplies(100), 4000);
  const [selected, setSelected] = useState<string | null>(null);

  const grouped: Map<string, ReplyLogEntry[]> = repliesPoll.data
    ? groupByConversation(repliesPoll.data.replies)
    : new Map();
  const conversationIds = Array.from(grouped.keys()).sort((a, b) => {
    const aLast = grouped.get(a)!.at(-1)!.logged_at;
    const bLast = grouped.get(b)!.at(-1)!.logged_at;
    return new Date(bLast).getTime() - new Date(aLast).getTime();
  });

  const selectedTurns = selected ? grouped.get(selected) ?? [] : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-nexora-text-bright">Conversation monitor</h1>
        <p className="text-sm text-nexora-muted mt-1">
          Live feed of every inbound reply NEXORA has processed, grouped by conversation. Polls every 4s.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversation list */}
        <Card title={`Active conversations (${conversationIds.length})`} className="lg:col-span-1">
          {repliesPoll.loading && !repliesPoll.data ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}
            </div>
          ) : repliesPoll.error && !repliesPoll.data ? (
            <ErrorState message={repliesPoll.error} />
          ) : conversationIds.length === 0 ? (
            <EmptyState
              title="No conversations yet"
              hint="Conversations appear here once /v1/reply is called for a merchant or customer turn."
            />
          ) : (
            <div className="flex flex-col gap-1 max-h-[600px] overflow-y-auto">
              {conversationIds.map((convId) => {
                const turns = grouped.get(convId)!;
                const last = turns.at(-1)!;
                const hasEnded = turns.some((t) => t.action === "end");
                  return (
                    <button
                      key={convId}
                      onClick={() => setSelected(convId)}
                      className={`text-left px-3.5 py-2.5 rounded-lg border transition-all duration-200 flex flex-col gap-1.5 ${
                        selected === convId
                          ? "border-indigo-500/25 bg-indigo-500/10 shadow-[0_0_12px_rgba(99,102,241,0.06)]"
                          : "border-transparent bg-white/2 hover:bg-white/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 w-full">
                        <span className="text-xs font-mono text-white truncate">{convId}</span>
                        {hasEnded && <Badge tone="danger">ended</Badge>}
                      </div>
                      <p className="text-xs text-slate-400 truncate w-full mt-0.5">{last.inbound_message}</p>
                    </button>
                  );
              })}
            </div>
          )}
        </Card>

        {/* Selected conversation timeline */}
        <Card
          title={selected ? `Timeline — ${selected}` : "Select a conversation"}
          className="lg:col-span-2"
        >
          {!selected ? (
            <EmptyState title="No conversation selected" hint="Choose a conversation from the list to see its turn-by-turn timeline." />
          ) : (
            <div className="flex flex-col gap-4 max-h-[600px] overflow-y-auto">
              {selectedTurns.map((turn, i) => {
                const prevTurn = selectedTurns[i - 1];
                const intentSwitch =
                  turn.explicit_commit && (!prevTurn || !prevTurn.explicit_commit);
                return (
                  <div key={`${turn.conversation_id}-${i}`} className="flex flex-col gap-3 w-full">
                    {intentSwitch && (
                      <div className="flex items-center gap-2 text-xs text-indigo-400 font-semibold my-1.5 uppercase tracking-wider">
                        <span className="h-px flex-1 bg-indigo-500/20" />
                        Switched to ACTION mode at turn {i + 1}
                        <span className="h-px flex-1 bg-indigo-500/20" />
                      </div>
                    )}
                    {/* Inbound Chat Bubble */}
                    <div className="flex flex-col gap-1.5 rounded-2xl p-3.5 border border-white/5 bg-white/3 max-w-[85%]">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] uppercase tracking-wider font-extrabold text-slate-400 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
                            Inbound
                          </span>
                          {turn.detected_language !== "en" && <Badge tone="accent">{turn.detected_language}</Badge>}
                        </div>
                        <span className="text-[10px] text-slate-500 font-semibold">
                          {new Date(turn.logged_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-200 leading-relaxed">{turn.inbound_message}</p>
                    </div>

                    {/* Bot response Chat Bubble */}
                    <div className="flex flex-col gap-1.5 rounded-2xl p-3.5 border border-indigo-500/15 bg-indigo-500/5 max-w-[85%] self-end ml-auto shadow-[0_0_20px_rgba(99,102,241,0.02)]">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge tone={actionTone(turn.action)}>{turn.action}</Badge>
                          {turn.cta && <Badge>{turn.cta}</Badge>}
                          {turn.wait_seconds != null && (
                            <span className="text-[9px] font-extrabold text-amber-400 uppercase bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                              wait {turn.wait_seconds}s
                            </span>
                          )}
                        </div>
                      </div>
                      {turn.body && <p className="text-sm text-white font-medium leading-relaxed">{turn.body}</p>}
                      {turn.rationale && (
                        <div className="border-t border-white/5 pt-2 mt-1">
                          <p className="text-xs text-slate-400 italic leading-relaxed">
                            <span className="font-mono text-indigo-400 text-[10px] not-italic mr-1.5 uppercase font-bold tracking-wider">
                              Rationale:
                            </span>
                            {turn.rationale}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
