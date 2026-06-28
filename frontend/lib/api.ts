const BOT_URL = process.env.NEXT_PUBLIC_BOT_URL || "http://localhost:8080";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BOT_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Could not reach bot at ${BOT_URL}${path}. Is the backend running?`, 0);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ? JSON.stringify(body.detail) : JSON.stringify(body);
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<T>;
}

// ── Types mirroring backend/models/requests.py + dashboard responses ──────
export interface HealthzResponse {
  status: "ok" | "degraded" | "down";
  uptime_seconds: number;
  contexts_loaded: { category: number; merchant: number; customer: number; trigger: number };
  mongo_connected: boolean;
  redis_connected: boolean;
}

export interface MetadataResponse {
  team_name: string;
  team_members: string[];
  model: string;
  approach: string;
  contact_email: string;
  version: string;
  submitted_at: string;
}

export interface ActionLogEntry {
  conversation_id: string;
  merchant_id: string | null;
  customer_id: string | null;
  send_as: string;
  trigger_id: string;
  template_name: string;
  template_params: string[];
  body: string;
  cta: string;
  suppression_key: string;
  rationale: string;
  taboo_hits?: string[];
  logged_at: string;
  confidence?: number;
  category?: string;
  trigger?: string;
}

export interface ReplyLogEntry {
  conversation_id: string;
  merchant_id: string | null;
  customer_id: string | null;
  inbound_message: string;
  action: "send" | "wait" | "end";
  body: string | null;
  cta: string | null;
  rationale: string;
  wait_seconds: number | null;
  explicit_commit: boolean;
  detected_language: string;
  logged_at: string;
}

export interface ContextSummary {
  scope: string;
  context_id: string;
  version: number;
  payload: Record<string, unknown>;
  delivered_at: string;
  stored_at: string;
}

export interface ConversationDetail {
  conversation_id: string;
  turns: Array<{ from: string; message: string; received_at?: string; turn_number?: number }>;
  sent_by_nexora: Array<{ body: string; sent_at: string }>;
  ended: boolean;
  auto_reply_count: number;
  replies_log: ReplyLogEntry[];
}

export interface StatsResponse {
  contexts_loaded: { category: number; merchant: number; customer: number; trigger: number };
  total_actions_logged: number;
  actions_by_template: Record<string, number>;
  actions_by_cta: Record<string, number>;
}

// ── Judge-facing endpoints (used by the simulator runner page) ─────────────
export interface TickAction {
  conversation_id: string;
  merchant_id: string | null;
  customer_id: string | null;
  send_as: string;
  trigger_id: string;
  template_name: string;
  template_params: string[];
  body: string;
  cta: string;
  suppression_key: string;
  rationale: string;
}

export interface ContextPushBody {
  scope: "category" | "merchant" | "customer" | "trigger";
  context_id: string;
  version: number;
  payload: Record<string, unknown>;
  delivered_at: string;
}

export interface ContextAckResponse {
  accepted: boolean;
  ack_id?: string | null;
  stored_at?: string | null;
  reason?: string | null;
  details?: string | null;
  current_version?: number | null;
}

// ── API surface ──────────────────────────────────────────────────────────
export const api = {
  botUrl: BOT_URL,

  healthz: () => request<HealthzResponse>("/v1/healthz"),
  metadata: () => request<MetadataResponse>("/v1/metadata"),

  listContexts: (scope?: string, limit = 100) =>
    request<{ contexts: ContextSummary[]; count: number }>(
      `/v1/dashboard/contexts${scope ? `?scope=${scope}&limit=${limit}` : `?limit=${limit}`}`
    ),
  getContext: (scope: string, contextId: string) =>
    request<{ context: ContextSummary | null }>(`/v1/dashboard/contexts/${scope}/${contextId}`),
  getContextHistory: (scope: string, contextId: string) =>
    request<{ history: ContextSummary[]; count: number }>(`/v1/dashboard/contexts/${scope}/${contextId}/history`),

  recentActions: (limit = 50) =>
    request<{ actions: ActionLogEntry[]; count: number }>(`/v1/dashboard/actions?limit=${limit}`),
  recentReplies: (limit = 50) =>
    request<{ replies: ReplyLogEntry[]; count: number }>(`/v1/dashboard/replies?limit=${limit}`),
  conversationDetail: (conversationId: string) =>
    request<ConversationDetail>(`/v1/dashboard/conversations/${encodeURIComponent(conversationId)}`),
  listConversations: (status?: string) =>
    request<{ conversations: any[]; count: number }>(
      `/v1/dashboard/conversations${status ? `?status=${status}` : ""}`
    ),
  simulateTickStreamUrl: (now: string, triggerIds: string[]) =>
    `${BOT_URL}/v1/dashboard/simulate_tick_stream?now=${encodeURIComponent(now)}&trigger_ids=${encodeURIComponent(triggerIds.join(","))}`,
  stats: () => request<any>("/v1/dashboard/stats"),

  pushContext: (body: ContextPushBody) =>
    request<ContextAckResponse>("/v1/context", { method: "POST", body: JSON.stringify(body) }),

  tick: (now: string, availableTriggers: string[]) =>
    request<{ actions: TickAction[] }>("/v1/tick", {
      method: "POST",
      body: JSON.stringify({ now, available_triggers: availableTriggers }),
    }),

  reply: (params: {
    conversation_id: string;
    merchant_id?: string | null;
    customer_id?: string | null;
    from_role: string;
    message: string;
    received_at: string;
    turn_number: number;
  }) => request<{ action: string; body?: string; cta?: string; rationale: string; wait_seconds?: number }>(
    "/v1/reply",
    { method: "POST", body: JSON.stringify(params) }
  ),

  teardown: () => request<{ status: string; redis_keys_deleted: number; mongo_documents_deleted: Record<string, number> }>(
    "/v1/teardown",
    { method: "POST" }
  ),
};
