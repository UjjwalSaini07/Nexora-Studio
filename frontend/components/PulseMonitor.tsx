"use client";

export function PulseMonitor({
  status,
  label,
}: {
  status: "ok" | "running" | "degraded" | "down";
  label: string;
}) {
  const isHealthy = status === "ok" || status === "running";
  
  // Status colors
  const color = isHealthy
    ? "#10b981" // Neon Emerald
    : status === "degraded"
    ? "#f59e0b" // Neon Amber
    : "#ef4444"; // Neon Red

  // Gradient colors
  const gradientStart = isHealthy ? "#10b981" : status === "degraded" ? "#fbbf24" : "#f87171";
  const gradientEnd = isHealthy ? "#06b6d4" : status === "degraded" ? "#f97316" : "#ef4444";

  return (
    <div className="flex items-center gap-3.5 select-none w-full min-w-0">
      {/* Oscilloscope Grid background and pulse wave */}
      <div className="relative w-28 h-9 shrink-0 bg-emerald-950/5 border border-white/5 rounded-lg overflow-hidden flex items-center justify-center">
        {/* Fine Coordinate Grid */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-20" aria-hidden="true">
          <defs>
            <pattern id="grid-pattern" width="8" height="8" patternUnits="userSpaceOnUse">
              <path d="M 8 0 L 0 0 0 8" fill="none" stroke="rgba(255, 255, 255, 0.15)" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-pattern)" />
          {/* Main horizontal sweep line */}
          <line x1="0" y1="18" x2="112" y2="18" stroke="rgba(255, 255, 255, 0.08)" strokeWidth="1" />
        </svg>

        {/* Pulse trace */}
        <svg width="112" height="36" viewBox="0 0 112 36" className="overflow-visible relative z-10" aria-hidden="true">
          <defs>
            <linearGradient id="pulse-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={gradientStart} />
              <stop offset="100%" stopColor={gradientEnd} />
            </linearGradient>
            <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Glowing pulse path mapped to 112px width */}
          <path
            d="M0,18 L20,18 L24,4 L28,32 L32,18 L40,18 L43,10 L46,26 L50,18 L65,18 L69,4 L73,32 L77,18 L85,18 L88,10 L91,26 L95,18 L112,18"
            fill="none"
            stroke="url(#pulse-gradient)"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#neon-glow)"
            className={status === "down" ? "" : "nexora-pulse-path"}
            style={status === "down" ? { strokeDasharray: "none" } : undefined}
          />
        </svg>

        {/* Ambient background glow orb */}
        {status !== "down" && (
          <div
            className="absolute w-8 h-8 rounded-full filter blur-[12px] opacity-10 pointer-events-none"
            style={{
              background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
              animation: "nexora-pulse-dot 1.8s ease-in-out infinite"
            }}
          />
        )}
      </div>

      {/* Label and Status description */}
      <div className="flex flex-col leading-tight min-w-0">
        <span className="text-[9px] uppercase tracking-wider text-nexora-muted font-bold font-mono truncate">{label}</span>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0 animate-ping"
            style={{ backgroundColor: color }}
          />
          <span
            className="text-sm font-semibold font-mono uppercase tracking-wide truncate"
            style={{ color, textShadow: `0 0 8px ${color}25` }}
          >
            {status}
          </span>
        </div>
      </div>
    </div>
  );
}
