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
        <h1 className="text-lg font-semibold text-vera-text-bright">Conversation monitor</h1>
        <p className="text-sm text-vera-muted mt-1">
          Live feed of every inbound reply VERA has processed, grouped by conversation. Polls every 4s.
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
                    className={`text-left px-3 py-2 rounded-lg border transition-colors ${
                      selected === convId
                        ? "border-vera-accent bg-vera-accent/10"
                        : "border-transparent hover:bg-vera-surface-raised"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-mono text-vera-text-bright truncate">{convId}</span>
                      {hasEnded && <Badge tone="danger">ended</Badge>}
                    </div>
                    <p className="text-xs text-vera-muted truncate mt-0.5">{last.inbound_message}</p>
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
                  <div key={`${turn.conversation_id}-${i}`} className="flex flex-col gap-2">
                    {intentSwitch && (
                      <div className="flex items-center gap-2 text-xs text-vera-accent font-medium">
                        <span className="h-px flex-1 bg-vera-accent/30" />
                        Switched to ACTION mode at turn {i + 1}
                        <span className="h-px flex-1 bg-vera-accent/30" />
                      </div>
                    )}
                    {/* Inbound */}
                    <div className="flex flex-col gap-1 pl-3 border-l-2 border-vera-border">
                      <div className="flex items-center gap-2">
                        <Badge>inbound</Badge>
                        {turn.detected_language !== "en" && <Badge tone="accent">{turn.detected_language}</Badge>}
                        <span className="text-xs text-vera-muted">
                          {new Date(turn.logged_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-vera-text">{turn.inbound_message}</p>
                    </div>
                    {/* Bot response */}
                    <div className="flex flex-col gap-1 pl-3 border-l-2 border-vera-accent/40 ml-4">
                      <div className="flex items-center gap-2">
                        <Badge tone={actionTone(turn.action)}>{turn.action}</Badge>
                        {turn.cta && <Badge>{turn.cta}</Badge>}
                        {turn.wait_seconds != null && (
                          <span className="text-xs text-vera-muted">wait {turn.wait_seconds}s</span>
                        )}
                      </div>
                      {turn.body && <p className="text-sm text-vera-text-bright">{turn.body}</p>}
                      <p className="text-xs text-vera-muted italic">{turn.rationale}</p>
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
