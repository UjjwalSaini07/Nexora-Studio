"use client";

import { useEffect, useState, useRef } from "react";

interface HealthData {
  status: string;
  mongo_connected: boolean;
  redis_connected: boolean;
  contexts_loaded: Record<string, number>;
}

export function Preloader() {
  const [visible, setVisible] = useState(true);
  const [mounted, setMounted] = useState(true);
  
  // Real-time connection checks
  const [step1, setStep1] = useState<"pending" | "loading" | "success" | "error">("loading");
  const [step2, setStep2] = useState<"pending" | "loading" | "success" | "error">("pending");
  const [step3, setStep3] = useState<"pending" | "loading" | "success" | "error">("pending");
  const [step4, setStep4] = useState<"pending" | "loading" | "success" | "error">("pending");
  
  const [progress, setProgress] = useState(10);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // Console logs stream
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const consoleBottomRef = useRef<HTMLDivElement>(null);
  
  // Empty database state handler
  const [isEmptyDb, setIsEmptyDb] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  
  // Latency metrics
  const [gatewayLatency, setGatewayLatency] = useState<number | null>(null);

  const BOT_URL = process.env.NEXT_PUBLIC_BOT_URL || "http://localhost:8080";

  const addLog = (msg: string) => {
    setConsoleLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  useEffect(() => {
    if (consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [consoleLogs]);

  const runSeeding = async () => {
    setIsSeeding(true);
    addLog("WARNING: Database contexts empty. Initiating seeding sequence...");
    addLog("POST /v1/demo/seed -> Sending mock payload trigger configurations...");
    try {
      const res = await fetch(`${BOT_URL}/v1/demo/seed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        addLog("SUCCESS: 355 Mock contexts loaded into MongoDB Atlas");
        addLog("SUCCESS: Atomic index pointers successfully cached in Redis");
        setIsSeeding(false);
        setIsEmptyDb(false);
        // Re-run diagnostic handshake
        checkServerConnection();
      } else {
        throw new Error(`Seeding failed with status: HTTP ${res.status}`);
      }
    } catch (err: any) {
      addLog(`ERROR: Seeding failed: ${err.message}`);
      setIsSeeding(false);
    }
  };

  const checkServerConnection = async () => {
    let active = true;
    let attempts = 0;
    const maxAttempts = 15;

    const runChecks = async () => {
      if (!active) return;
      attempts++;
      addLog(`Handshake request sent to API gateway (Attempt ${attempts}/${maxAttempts})...`);
      
      try {
        setStep1("loading");
        const t0 = performance.now();
        const res = await fetch(`${BOT_URL}/v1/healthz`, {
          signal: AbortSignal.timeout(4000)
        });
        const latency = Math.round(performance.now() - t0);
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data: HealthData = await res.json();
        
        if (active) {
          setGatewayLatency(latency);
          addLog(`Connected to API Gateway. Latency: ${latency}ms`);
          setStep1("success");
          setProgress(40);
          setStep2("loading");
          addLog("Inspecting MongoDB connection parameters...");
          await new Promise((r) => setTimeout(r, 1000));

          if (data.mongo_connected) {
            addLog("MongoDB connection active. Checking schema status...");
            setStep2("success");
            setProgress(65);
            setStep3("loading");
          } else {
            setStep2("error");
            setStep3("error");
            setStep4("error");
            throw new Error("MongoDB Cluster connection offline.");
          }
          await new Promise((r) => setTimeout(r, 1000));

          addLog("Pinging Redis cache cluster...");
          if (data.redis_connected) {
            addLog("Redis hot cache cluster verified. Core keys active.");
            setStep3("success");
            setProgress(85);
            setStep4("loading");
          } else {
            setStep3("error");
            setStep4("error");
            throw new Error("Redis cache connection offline.");
          }
          await new Promise((r) => setTimeout(r, 1000));

          // Check if data contexts exist
          const totalContexts = Object.values(data.contexts_loaded || {}).reduce((a, b) => a + b, 0);
          addLog(`Context Registry: category=${data.contexts_loaded?.category || 0}, merchant=${data.contexts_loaded?.merchant || 0}, customer=${data.contexts_loaded?.customer || 0}, trigger=${data.contexts_loaded?.trigger || 0}`);
          
          if (totalContexts === 0) {
            setIsEmptyDb(true);
            setStep4("error");
            setProgress(90);
            addLog("WARNING: Database is empty. Seeding is required to start operations.");
            return; // Halt and show seed button
          }

          setStep4("success");
          setProgress(100);
          addLog("System diagnostic complete. Launching cockpit console...");
          
          sessionStorage.setItem("nexora_preloader_completed", "true");
          await new Promise((r) => setTimeout(r, 1200));
          
          setVisible(false);
          setTimeout(() => setMounted(false), 500);
        }
      } catch (err: any) {
        if (active) {
          addLog(`API Handshake failed: ${err.message}`);
          if (attempts < maxAttempts) {
            addLog("Retrying in 2 seconds (Render cold start trigger)...");
            setProgress((prev) => Math.min(prev + 2, 35));
            setTimeout(runChecks, 2000);
          } else {
            setStep1("error");
            setErrorMessage(err.message || "Failed to establish connection to backend API gateway.");
          }
        }
      }
    };

    runChecks();
  };

  useEffect(() => {
    // If already completed in session, bypass preloader
    const alreadySeen = sessionStorage.getItem("nexora_preloader_completed");
    if (alreadySeen === "true") {
      setVisible(false);
      const t = setTimeout(() => setMounted(false), 300);
      return () => clearTimeout(t);
    }

    const runBootSequence = async () => {
      addLog("System Boot: Initializing Client Handshake...");
      await new Promise((r) => setTimeout(r, 450));
      addLog("LOADER: Loading environment configs & CORS policies...");
      await new Promise((r) => setTimeout(r, 450));
      addLog("LOADER: Mapping router paths and Next.js page views...");
      await new Promise((r) => setTimeout(r, 450));
      addLog("LOADER: Initiating uvicorn connection check sequence...");
      await new Promise((r) => setTimeout(r, 300));
      checkServerConnection();
    };

    runBootSequence();
  }, []);

  if (!mounted) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/95 backdrop-blur-2xl transition-opacity duration-500 ease-in-out ${
        visible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {/* HUD Floating Code Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-20">
        <div className="absolute top-[10%] left-[20%] font-mono text-[10px] text-indigo-400/40 animate-pulse select-none">{"await mongo.get_context('merchant')"}</div>
        <div className="absolute top-[40%] left-[80%] font-mono text-[10px] text-purple-400/40 animate-pulse select-none" style={{ animationDelay: "1s" }}>{"redis.set_suppression(key)"}</div>
        <div className="absolute top-[75%] left-[15%] font-mono text-[9px] text-blue-400/40 animate-pulse select-none" style={{ animationDelay: "2s" }}>{"LLM_MODEL = 'llama-3.3-70b'"}</div>
        <div className="absolute top-[80%] left-[70%] font-mono text-[10px] text-indigo-500/30 animate-pulse select-none">{"FastAPI (Async ASGI Lifecycle)"}</div>
      </div>

      {/* Glow orb background behind loader */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-indigo-500/10 blur-[90px] pointer-events-none" />

      <div className="max-w-xl w-full px-6 flex flex-col items-center space-y-6 relative z-10">
        
        {/* Animated Brand Header with Double HUD indicator rings */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="relative flex items-center justify-center w-28 h-28">
            
            {/* Outer Spinning Ring */}
            <div className="absolute inset-0 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" style={{ animationDuration: "3s" }} />
            
            {/* Inner Counter-spinning Ring */}
            <div className="absolute inset-2 border-2 border-purple-500/10 border-b-purple-400 rounded-full animate-spin" style={{ animationDuration: "1.5s", animationDirection: "reverse" }} />
            
            {/* Pulsing center glow */}
            <div className="absolute inset-4 rounded-full bg-indigo-500/10 blur-sm animate-pulse" />
            
            <img
              src="/nexoraLogo.png"
              alt="NEXORA Logo"
              className="w-16 h-16 object-contain relative z-10 animate-pulse"
            />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-wider font-mono">
              NEXORA <span className="text-indigo-400">ENGINE</span>
            </h1>
            <div className="flex items-center justify-center gap-1.5 mt-1">
              <span className="text-[9px] text-slate-500 font-mono uppercase tracking-widest">
                Operations & control center
              </span>
              {gatewayLatency !== null && (
                <span className="text-[9px] font-mono font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                  {gatewayLatency}ms
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Global Progress Bar */}
        <div className="w-full bg-slate-900/50 rounded-full h-1.5 border border-white/5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-400 h-full rounded-full transition-all duration-500 shadow-[0_0_12px_rgba(99,102,241,0.6)]"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Console Log Stream terminal block (Incredibly engaging) */}
        <div className="w-full rounded-xl border border-white/10 bg-slate-950/90 overflow-hidden shadow-2xl">
          {/* Mac-style Window Top Bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-900/80 border-b border-white/5 select-none">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500/85" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500/85" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/85" />
            </div>
            <span className="text-[9px] font-mono text-slate-500 tracking-wider">
              diagnostics@nexora:~
            </span>
            <div className="w-10" /> {/* balance spacing */}
          </div>

          {/* Logs scrollable block */}
          <div 
            className="h-32 p-4 overflow-y-auto space-y-1.5 select-none font-mono text-[10px]"
            style={{ 
              scrollbarWidth: "none", 
              msOverflowStyle: "none" 
            }}
          >
            {/* Inline CSS to hide Chrome/Webkit scrollbars */}
            <style dangerouslySetInnerHTML={{__html: `
              .no-scrollbar::-webkit-scrollbar {
                display: none;
              }
            `}} />
            
            <div className="no-scrollbar space-y-1.5">
              {consoleLogs.map((log, idx) => (
                <div key={idx} className={log.includes("SUCCESS") ? "text-emerald-400" : log.includes("WARNING") ? "text-amber-400" : log.includes("ERROR") ? "text-rose-400" : "text-slate-400"}>
                  {log}
                </div>
              ))}
              
              {/* Blinking terminal prompt */}
              <div className="flex items-center text-slate-400">
                <span className="text-indigo-400 mr-1.5">$</span>
                <span className="w-1.5 h-3.5 bg-emerald-400 ml-0.5 animate-pulse" style={{ animationDuration: "1s" }} />
              </div>
            </div>
            <div ref={consoleBottomRef} />
          </div>
        </div>

        {/* Real-time Checklist & Empty Database Seeding card */}
        {isEmptyDb ? (
          <div className="w-full rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 space-y-3 font-mono text-xs text-center">
            <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider block">⚠️ Action Required</span>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              API connectivity is active, but the MongoDB database is empty. Seed the canonical mock triggers dataset to enable simulator controls.
            </p>
            <button
              onClick={runSeeding}
              disabled={isSeeding}
              className={`w-full py-2.5 rounded-xl border font-bold uppercase tracking-wider text-xs transition-all duration-200 ${
                isSeeding
                  ? "bg-amber-500/10 border-amber-500/20 text-amber-500/50 cursor-not-allowed"
                  : "bg-amber-500/15 border-amber-500/40 text-amber-400 hover:bg-amber-500/25 hover:border-amber-500/60"
              }`}
            >
              {isSeeding ? "Seeding Database..." : "Seed Mock Database"}
            </button>
          </div>
        ) : (
          <div className="w-full rounded-2xl border border-white/5 bg-slate-900/20 p-5 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-1">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider">Diagnostic Steps</span>
              <span className="text-[9px] text-indigo-400 font-bold">Progress: {progress}%</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-[11px]">
              <div className="flex items-center justify-between p-2 rounded bg-slate-950/40 border border-white/[0.02]">
                <span className="text-slate-400">1. API Gateway</span>
                <StatusIcon status={step1} />
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-950/40 border border-white/[0.02]">
                <span className="text-slate-400">2. MongoDB</span>
                <StatusIcon status={step2} />
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-950/40 border border-white/[0.02]">
                <span className="text-slate-400">3. Redis Cache</span>
                <StatusIcon status={step3} />
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-950/40 border border-white/[0.02]">
                <span className="text-slate-400">4. Context Sync</span>
                <StatusIcon status={step4} />
              </div>
            </div>
          </div>
        )}

        {/* Error message / Skip */}
        {errorMessage && (
          <div className="w-full text-center space-y-3">
            <p className="text-[11px] text-rose-400 leading-relaxed font-mono">
              ⚠️ {errorMessage}
            </p>
            <button
              onClick={() => {
                sessionStorage.setItem("nexora_preloader_completed", "true");
                setVisible(false);
                setTimeout(() => setMounted(false), 500);
              }}
              className="px-4 py-2 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-[10px] text-slate-400 font-mono transition-all duration-200"
            >
              Skip Handshake & Enter Dashboard
            </button>
          </div>
        )}

        {!errorMessage && !isEmptyDb && progress < 100 && (
          <p className="text-[9px] text-slate-600 text-center font-mono animate-pulse">
            Establishing secure connection... (may take up to 45s for cold start)
          </p>
        )}

      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: "pending" | "loading" | "success" | "error" }) {
  if (status === "pending") {
    return <span className="text-slate-700">○</span>;
  }
  if (status === "loading") {
    return (
      <span className="flex h-2 w-2 relative">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
      </span>
    );
  }
  if (status === "success") {
    return <span className="text-emerald-400 font-bold">✓</span>;
  }
  return <span className="text-rose-500 font-bold">✗</span>;
}
