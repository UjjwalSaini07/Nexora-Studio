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
    <div className={`bg-nexora-surface border border-nexora-border rounded-xl p-5 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          {title && <h2 className="text-sm font-semibold text-nexora-text-bright tracking-tight">{title}</h2>}
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
    default: "text-nexora-text-bright",
    success: "text-nexora-success",
    warn: "text-nexora-warn",
    danger: "text-nexora-danger",
  }[tone];

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wider text-nexora-muted">{label}</span>
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
    default: "bg-nexora-surface-raised text-nexora-muted border-nexora-border",
    success: "bg-nexora-success/10 text-nexora-success border-nexora-success/30",
    warn: "bg-nexora-warn/10 text-nexora-warn border-nexora-warn/30",
    danger: "bg-nexora-danger/10 text-nexora-danger border-nexora-danger/30",
    accent: "bg-nexora-accent/10 text-nexora-accent border-nexora-accent/30",
  }[tone];

  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border ${styles}`}>
      {children}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-4">
      <p className="text-sm font-medium text-nexora-text">{title}</p>
      {hint && <p className="text-xs text-nexora-muted mt-1 max-w-sm">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-4">
      <Badge tone="danger">Connection error</Badge>
      <p className="text-xs text-nexora-muted mt-2 max-w-sm font-mono">{message}</p>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-nexora-surface-raised rounded ${className}`} />;
}

export function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="font-mono text-xs bg-nexora-bg border border-nexora-border rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words text-nexora-text">
      {children}
    </pre>
  );
}
