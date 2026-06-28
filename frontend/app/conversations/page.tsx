"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

function actionTone(action: string): "success" | "warn" | "danger" | "default" {
  if (action === "send") return "success";
  if (action === "wait") return "warn";
  if (action === "end") return "danger";
  return "default";
}

function statusTone(status: string): "success" | "warn" | "danger" | "accent" | "default" {
  if (status === "Resolved") return "danger";
  if (status === "Suppressed") return "accent";
  if (status === "Waiting") return "warn";
  if (status === "High Priority") return "danger";
  return "success";
}

function getCategoryColor(cat: string): string {
  const c = cat.toLowerCase();
  if (c.includes("dentist")) return "bg-blue-500/10 border-blue-500/20 text-blue-400";
  if (c.includes("salon")) return "bg-pink-500/10 border-pink-500/20 text-pink-400";
  if (c.includes("gym")) return "bg-purple-500/10 border-purple-500/20 text-purple-400";
  if (c.includes("pharmaci") || c.includes("pharmac")) return "bg-emerald-500/10 border-emerald-500/20 text-emerald-400";
  if (c.includes("restaur")) return "bg-orange-500/10 border-orange-500/20 text-orange-400";
  return "bg-slate-500/10 border-slate-500/20 text-slate-400";
}

export default function ConversationsPage() {
  const [filter, setFilter] = useState<string>("all");
  const [selected, setSelected] = useState<string | null>(null);

  // Poll conversations endpoint with status filter
  const conversationsPoll = usePolling(
    () => api.listConversations(filter === "all" ? undefined : filter),
    4000,
    [filter]
  );

  const conversations = conversationsPoll.data?.conversations ?? [];
  const selectedConv = selected ? conversations.find(c => c.conversation_id === selected) : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-nexora-text-bright">Operations Conversation Console</h1>
          <p className="text-sm text-nexora-muted mt-1">
            Live multi-turn conversation logs and decision flows grouped by conversation ID.
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex items-center gap-1.5 bg-white/2 border border-white/5 p-1 rounded-xl backdrop-blur-sm self-start md:self-auto">
          {["all", "Active", "Resolved", "Waiting", "Suppressed", "High Priority"].map((status) => (
            <button
              key={status}
              onClick={() => {
                setFilter(status);
                setSelected(null); // clear selection on filter change
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all uppercase tracking-wider ${
                filter === status
                  ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/10"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversation list */}
        <Card title={`Conversations (${conversations.length})`} className="lg:col-span-1">
          {conversationsPoll.loading && !conversationsPoll.data ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}
            </div>
          ) : conversationsPoll.error && !conversationsPoll.data ? (
            <ErrorState message={conversationsPoll.error} />
          ) : conversations.length === 0 ? (
            <EmptyState
              title="No matching conversations"
              hint="No records found in database matching this filter status."
            />
          ) : (
            <div className="flex flex-col gap-2.5 max-h-[650px] overflow-y-auto pr-1">
              {conversations.map((conv) => {
                const isSel = selected === conv.conversation_id;
                const catColor = getCategoryColor(conv.merchant_category);
                return (
                  <button
                    key={conv.conversation_id}
                    onClick={() => setSelected(conv.conversation_id)}
                    className={`text-left px-4 py-3 rounded-xl border transition-all duration-200 flex flex-col gap-2 ${
                      isSel
                        ? "border-indigo-500/30 bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.08)]"
                        : "border-transparent bg-white/2 hover:bg-white/5"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 w-full">
                      <div className="flex items-center gap-2.5 min-w-0">
                        {/* Avatar */}
                        <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center font-bold text-xs uppercase ${catColor}`}>
                          {conv.merchant_name.slice(0, 2)}
                        </div>
                        <div className="flex flex-col min-w-0">
                          <span className="text-sm font-medium text-white truncate">{conv.merchant_name}</span>
                          <span className="text-[10px] font-mono text-slate-400 truncate">{conv.conversation_id}</span>
                        </div>
                      </div>
                      <Badge tone={statusTone(conv.status)}>
                        {conv.status}
                      </Badge>
                    </div>

                    <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed bg-black/20 p-2 rounded-lg border border-white/5">
                      {conv.latest_message}
                    </p>

                    <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-slate-400 flex-wrap">
                      <span className="capitalize">{conv.merchant_category}</span>
                      <div className="flex items-center gap-2">
                        <span>Turns: <strong className="text-slate-200">{conv.reply_count}</strong></span>
                        {conv.suppression_state && <span className="text-pink-400">● Suppressed</span>}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Card>

        {/* Selected conversation timeline */}
        <Card
          title={selectedConv ? `Audit timeline — ${selectedConv.merchant_name}` : "Audit details"}
          className="lg:col-span-2"
        >
          {!selectedConv ? (
            <EmptyState title="No conversation selected" hint="Choose a conversation from the sidebar list to audit its execution timeline." />
          ) : (
            <div className="flex flex-col gap-6 max-h-[650px] overflow-y-auto pr-1">
              {/* Metadata Overview Panel */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl border border-white/5 bg-white/1 font-mono text-xs text-slate-300">
                <div className="flex flex-col gap-1">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500">Trigger Kind</span>
                  <span className="font-semibold text-indigo-400 truncate" title={selectedConv.trigger}>{selectedConv.trigger}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500">Template</span>
                  <span className="font-semibold text-indigo-400 truncate" title={selectedConv.selected_template}>{selectedConv.selected_template}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500">Latest Confidence</span>
                  <span className="font-semibold text-emerald-400">{Math.round(selectedConv.confidence * 100)}%</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[9px] uppercase tracking-wider text-slate-500">Auto Suppress</span>
                  <span className="font-semibold">{selectedConv.suppression_state ? "Enabled" : "Disabled"}</span>
                </div>
              </div>

              {/* Message Timeline */}
              <div className="flex flex-col gap-4">
                {selectedConv.timeline.map((turn: any, i: number) => {
                  const isInbound = turn.type === "inbound";
                  const isAction = turn.type === "action";
                  
                  if (isInbound) {
                    return (
                      <div key={i} className="flex flex-col gap-1 rounded-2xl p-4 border border-white/5 bg-white/3 max-w-[85%]">
                        <div className="flex items-center justify-between gap-4">
                          <span className="text-[9px] uppercase tracking-wider font-extrabold text-slate-400 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
                            Inbound ({turn.from})
                          </span>
                          <span className="text-[10px] text-slate-500 font-semibold font-mono">
                            {new Date(turn.logged_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-sm text-slate-200 leading-relaxed mt-1.5">{turn.message}</p>
                      </div>
                    );
                  }

                  // Outbound Action or Outbound Reply
                  return (
                    <div key={i} className="flex flex-col gap-1 rounded-2xl p-4 border border-indigo-500/15 bg-indigo-500/5 max-w-[85%] self-end ml-auto shadow-[0_0_25px_rgba(99,102,241,0.02)]">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge tone={isAction ? "success" : actionTone(turn.action)}>
                            Outbound ({isAction ? "tick" : turn.action})
                          </Badge>
                          {turn.cta && turn.cta !== "none" && <Badge>{turn.cta}</Badge>}
                          <span className="text-[9px] font-mono text-emerald-400 uppercase bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                            {Math.round(turn.confidence * 100)}% Confidence
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 font-semibold font-mono">
                          {new Date(turn.logged_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-white font-medium leading-relaxed mt-2">{turn.message}</p>
                      
                      {turn.rationale && (
                        <div className="border-t border-white/5 pt-2.5 mt-2.5 flex flex-col gap-1">
                          <span className="font-mono text-indigo-400 text-[10px] uppercase font-bold tracking-wider">
                            Decision Rationale:
                          </span>
                          <p className="text-xs text-slate-400 italic leading-relaxed">
                            {turn.rationale}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
