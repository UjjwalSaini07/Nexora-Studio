"use client";

import { useEffect, useState } from "react";

interface HealthStatus {
  status: string;
  uptime_seconds: number;
  mongo_connected: boolean;
  redis_connected: boolean;
}

export function Footer() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [statusState, setStatusState] = useState<"loading" | "online" | "degraded" | "offline">("loading");

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const botUrl = process.env.NEXT_PUBLIC_BOT_URL || "http://localhost:8080";
        const res = await fetch(`${botUrl}/v1/healthz`, {
          signal: AbortSignal.timeout(4000) // 4s timeout
        });
        if (res.ok) {
          const data: HealthStatus = await res.json();
          setHealth(data);
          if (data.status === "ok") {
            setStatusState("online");
          } else {
            setStatusState("degraded");
          }
        } else {
          setStatusState("degraded");
        }
      } catch (err) {
        setStatusState("offline");
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    return `${hrs}h ${remainingMins}m`;
  };

  return (
    <footer className="w-full px-6 pb-10 pt-4 relative z-10">
      <div className="mx-auto max-w-7xl">
        <div className="rounded-2xl border border-indigo-500/10 bg-slate-950/40 backdrop-blur-xl p-6 md:p-8 flex flex-col lg:flex-row items-center justify-between gap-6 shadow-[0_8px_32px_rgba(0,0,0,0.37)] transition-all duration-300 hover:border-indigo-500/15">
          
          {/* Left Block: Brand & Live Health Status */}
          <div className="flex flex-col md:flex-row items-center md:items-start gap-5">
            <div className="relative group shrink-0">
              <div className="absolute inset-0 bg-indigo-500/20 rounded-full blur-md opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
              <img 
                src="/nexoraLogo.png" 
                alt="NEXORA AI Logo" 
                className="w-12 h-12 object-contain shrink-0 relative z-10 transition-transform duration-500 group-hover:scale-105" 
              />
            </div>
            <div className="text-center md:text-left">
              <div className="flex flex-wrap items-center justify-center md:justify-start gap-2.5">
                <span className="font-mono text-sm font-bold tracking-widest text-white">
                  NEXORA ENGINE
                </span>
                
                {/* Dynamic Status Indicator Pill */}
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-mono font-semibold tracking-wider uppercase transition-all duration-300 ${
                  statusState === "online" 
                    ? "bg-emerald-500/5 text-emerald-400 border-emerald-500/20 shadow-[0_0_8px_rgba(16,185,129,0.1)]" 
                    : statusState === "degraded"
                    ? "bg-amber-500/5 text-amber-400 border-amber-500/20 shadow-[0_0_8px_rgba(245,158,11,0.1)]"
                    : statusState === "offline"
                    ? "bg-rose-500/5 text-rose-400 border-rose-500/20 shadow-[0_0_8px_rgba(244,63,94,0.1)]"
                    : "bg-slate-500/5 text-slate-400 border-slate-500/20"
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full relative flex shrink-0 ${
                    statusState === "online" ? "bg-emerald-500" :
                    statusState === "degraded" ? "bg-amber-500" :
                    statusState === "offline" ? "bg-rose-500" : "bg-slate-500"
                  }`}>
                    {statusState !== "loading" && (
                      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                        statusState === "online" ? "bg-emerald-400" :
                        statusState === "degraded" ? "bg-amber-400" :
                        statusState === "offline" ? "bg-rose-400" : "bg-slate-400"
                      }`} />
                    )}
                  </span>
                  {statusState === "online" && "Operational"}
                  {statusState === "degraded" && "Degraded Status"}
                  {statusState === "offline" && "System Offline"}
                  {statusState === "loading" && "Resolving Status"}
                </div>
              </div>
              <p className="text-[11px] text-slate-400 max-w-sm mt-2 leading-relaxed">
                Real-time cognitive orchestration layer for the magicpin AI Challenge.
              </p>
            </div>
          </div>

          {/* Middle Block: Live DB Connections */}
          <div className="flex flex-col items-center lg:items-start gap-2 px-6 py-2 border-y border-white/5 lg:border-y-0 lg:border-x lg:border-white/5 lg:px-8 shrink-0">
            <span className="text-[10px] font-mono tracking-widest text-slate-500 uppercase">Datastores Monitor</span>
            <div className="flex gap-4 text-[10px] font-mono">
              <div className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${health?.mongo_connected ? "bg-emerald-500" : "bg-rose-500"}`} />
                <span className="text-slate-300">MongoDB</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${health?.redis_connected ? "bg-emerald-500" : "bg-rose-500"}`} />
                <span className="text-slate-300">Redis</span>
              </div>
              {health?.uptime_seconds !== undefined && (
                <div className="text-slate-500 ml-1">
                  Uptime: <span className="text-indigo-400">{formatUptime(health.uptime_seconds)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Right Block: Author & Navigation */}
          <div className="flex flex-col items-center lg:items-end gap-3 shrink-0">
            <div className="text-center lg:text-right text-xs">
              <span className="text-slate-500">Architected & Designed by </span>
              <a 
                href="https://ujjwalsaini.vercel.app" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="font-semibold text-white hover:text-indigo-400 hover:[text-shadow:0_0_8px_rgba(99,102,241,0.3)] transition-all duration-300"
              >
                Ujjwal Saini
              </a>
            </div>
            
            <div className="flex gap-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <a 
                href="https://github.com/UjjwalSaini07" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="hover:text-indigo-400 hover:[text-shadow:0_0_8px_rgba(99,102,241,0.4)] transition-all duration-300"
              >
                GitHub
              </a>
              <a 
                href="https://ujjwalsaini.vercel.app" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="hover:text-indigo-400 hover:[text-shadow:0_0_8px_rgba(99,102,241,0.4)] transition-all duration-300"
              >
                Portfolio
              </a>
            </div>
          </div>

        </div>
      </div>
    </footer>
  );
}
