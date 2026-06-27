// frontend/components/PulseMonitor.tsx
"use client";

/**
 * The signature element. NEXORA is described as the "living heartbeat" of
 * merchant engagement, so the live-ops header doesn't get a generic spinner
 * or progress bar — it gets an actual ECG-style trace. The line redraws on
 * a loop via stroke-dashoffset animation, and the leading dot pulses in
 * sync, so it reads as "this system is alive right now" rather than
 * "this page is loading."
 *
 * `status` controls the trace color: ok -> accent blue, degraded -> amber,
 * down -> red flat-line (no animation — a flat-lined trace is itself the
 * signal that something is wrong).
 */
export function PulseMonitor({
  status,
  label,
}: {
  status: "ok" | "degraded" | "down";
  label: string;
}) {
  const color =
    status === "ok" ? "var(--nexora-accent)" : status === "degraded" ? "var(--nexora-warn)" : "var(--nexora-danger)";

  return (
    <div className="flex items-center gap-3">
      <svg width="120" height="32" viewBox="0 0 120 32" className="overflow-visible" aria-hidden="true">
        <path
          d="M0,16 L20,16 L26,4 L32,28 L38,16 L48,16 L52,10 L56,22 L60,16 L120,16"
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={status === "down" ? "" : "nexora-pulse-path"}
          style={status === "down" ? { strokeDasharray: "none" } : undefined}
        />
        {status !== "down" && (
          <circle cx="60" cy="16" r="3" fill={color} className="nexora-pulse-dot" />
        )}
      </svg>
      <div className="flex flex-col leading-tight">
        <span className="text-xs uppercase tracking-wider text-nexora-muted">{label}</span>
        <span
          className="text-sm font-semibold capitalize"
          style={{ color }}
        >
          {status}
        </span>
      </div>
    </div>
  );
}
