// frontend/components/ui.tsx
import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <div className={`glass-panel glass-panel-hover p-5 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
          {title && (
            <h2 className="text-sm font-semibold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function MetricStat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const toneColor = {
    default: "text-white [text-shadow:0_0_12px_rgba(255,255,255,0.15)]",
    success: "text-emerald-400 [text-shadow:0_0_12px_rgba(16,185,129,0.25)]",
    warn: "text-amber-400 [text-shadow:0_0_12px_rgba(245,158,11,0.25)]",
    danger: "text-rose-400 [text-shadow:0_0_12px_rgba(239,68,68,0.25)]",
  }[tone];

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wider text-slate-400 font-medium">{label}</span>
      <span className={`text-2xl font-bold tabular-nums tracking-tight ${toneColor}`}>{value}</span>
    </div>
  );
}

export function Badge({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "success" | "warn" | "danger" | "accent";
}) {
  const styles = {
    default: "bg-white/5 text-slate-300 border-white/10 [text-shadow:0_0_8px_rgba(255,255,255,0.1)]",
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.06)]",
    warn: "bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.06)]",
    danger: "bg-rose-500/10 text-rose-400 border-rose-500/20 shadow-[0_0_10px_rgba(244,63,94,0.06)]",
    accent: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20 shadow-[0_0_10px_rgba(99,102,241,0.06)]",
  }[tone];

  return (
    <span className={`inline-flex items-center text-[10px] uppercase tracking-wider font-semibold px-2.5 py-0.5 rounded-full border backdrop-blur-md ${styles}`}>
      {children}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-4">
      <p className="text-sm font-medium text-white">{title}</p>
      {hint && <p className="text-xs text-slate-400 mt-1.5 max-w-sm">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-4">
      <Badge tone="danger">Connection error</Badge>
      <p className="text-xs text-slate-400 mt-3.5 max-w-sm font-mono">{message}</p>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-white/5 border border-white/5 rounded ${className}`} />;
}

export function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="font-mono text-xs bg-black/50 border border-white/5 rounded-lg p-3.5 overflow-x-auto whitespace-pre-wrap break-words text-slate-300 shadow-inner backdrop-blur-sm">
      {children}
    </pre>
  );
}
