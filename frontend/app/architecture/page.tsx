"use client";

import { useState, useEffect } from "react";

// Kind weights lookup table matching the Priority Engine
const KIND_WEIGHTS: Record<string, number> = {
  "supply_alert": 20,
  "regulation_change": 20,
  "appointment_tomorrow": 18,
  "recall_due": 18,
  "chronic_refill_due": 18,
  "renewal_due": 16,
  "perf_spike": 15,
  "perf_dip": 14,
  "seasonal_perf_dip": 14,
  "competitor_opened": 14,
  "customer_lapsed_hard": 13,
  "winback_eligible": 12,
  "bridal_followup": 12,
  "wedding_package_followup": 12,
  "trial_followup": 11,
  "customer_lapsed_soft": 10,
  "ipl_match_today": 13,
  "festival_upcoming": 12,
  "category_seasonal": 10,
  "milestone_reached": 9,
  "review_theme_emerged": 9,
  "gbp_unverified": 9,
  "cde_opportunity": 9,
  "research_digest": 8,
  "active_planning_intent": 8,
  "dormant_with_nexora": 6,
  "curious_ask_due": 5,
};

interface InterviewTurn {
  question: string;
  answer: string;
}

const INTERVIEW_TURNS: Record<string, InterviewTurn> = {
  challenge: {
    question: "What was the most complex architectural challenge?",
    answer: "Building the Redis-backed multi-turn wait-state machine. It had to atomically handle WhatsApp auto-reply detection and intent transitions while preserving rate limits, ensuring the system never duplicates outbound events or blocks active client threads.",
  },
  models: {
    question: "Why Llama 3.3 70B and Groq LPUs?",
    answer: "Llama 3.3 70B offers state-of-the-art reasoning for complex trigger evaluations. Running it on Groq's LPUs gives us sub-second text completions, keeping our overall processing latency well below the 30-second challenge SLA budget.",
  },
  idempotency: {
    question: "How is database versioning and consistency managed?",
    answer: "We built a monotonic version checking system. Pushed contexts must have incrementing version counts. Redis checks these versions atomically at ingestion time, rejecting stale or out-of-order payloads to prevent data race conditions.",
  },
  vision: {
    question: "What is your long-term engineering vision for NEXORA?",
    answer: "Scaling it into a fully multimodal, event-driven orchestration mesh. By introducing asynchronous worker queues (Celery/RabbitMQ) and Vector store RAG frameworks, it can analyze live merchant images, voice notes, and history logs instantly.",
  },
};

export default function ArchitecturePage() {
  // --- Interview Chat Simulator State ---
  const [selectedTopic, setSelectedTopic] = useState<string>("challenge");
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [displayedAnswer, setDisplayedAnswer] = useState<string>(INTERVIEW_TURNS.challenge.answer);

  // Trigger typing effect when topic changes
  useEffect(() => {
    setIsTyping(true);
    const timer = setTimeout(() => {
      setIsTyping(false);
      setDisplayedAnswer(INTERVIEW_TURNS[selectedTopic].answer);
    }, 600); // simulated typing delay
    return () => clearTimeout(timer);
  }, [selectedTopic]);

  // --- Priority Calculator State ---
  const [urgency, setUrgency] = useState<number>(3);
  const [expiryHours, setExpiryHours] = useState<number>(48);
  const [triggerKind, setTriggerKind] = useState<string>("appointment_tomorrow");
  const [source, setSource] = useState<"internal" | "external">("external");
  const [scope, setScope] = useState<"customer" | "merchant">("customer");
  const [payloadKeys, setPayloadKeys] = useState<number>(4);

  // --- Calculate Priority Math ---
  const urgencyPts = urgency * 5;
  
  let expiryPts = 12; // default neutral
  if (expiryHours <= 24) {
    expiryPts = 25;
  } else if (expiryHours >= 168) {
    expiryPts = 0;
  } else {
    const ratio = 1 - (expiryHours - 24) / (168 - 24);
    expiryPts = Math.floor(ratio * 25);
  }

  const kindPts = KIND_WEIGHTS[triggerKind] || 7;
  const sourcePts = source === "external" ? 10 : 6;
  const scopePts = scope === "customer" ? 10 : 7;
  const payloadPts = Math.min(10, payloadKeys * 2);

  const totalPriorityScore = Math.min(100, urgencyPts + expiryPts + kindPts + sourcePts + scopePts + payloadPts);

  return (
    <div className="space-y-12 pb-16">
      {/* Page Header */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs uppercase tracking-widest font-extrabold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded px-2.5 py-1">
            CORE PLATFORM
          </span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Author & Engine Architecture
        </h1>
        <p className="max-w-3xl text-sm text-slate-400 leading-relaxed">
          NEXORA combines structured context injection, real-time message prioritization, and heuristic conversational state machines. Explore the modules below to test the engines.
        </p>
      </div>

      {/* Premium Author Details & Interactive Q&A Segment */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Enriched & Highly Aesthetic Author Profile Card */}
        <div className="lg:col-span-1 rounded-2xl border border-indigo-500/10 bg-gradient-to-b from-slate-950/60 to-slate-900/40 backdrop-blur-xl p-6 relative overflow-hidden group shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-all duration-300 hover:border-indigo-500/25">
          {/* Animated Ambient background orb inside card */}
          <div className="absolute top-[-20%] left-[-20%] w-40 h-40 rounded-full bg-indigo-500/10 blur-2xl group-hover:bg-indigo-500/15 transition-all duration-500 pointer-events-none" />
          
          <div className="flex flex-col items-center text-center space-y-5 relative z-10">
            {/* Avatar Glow Component */}
            <div className="relative cursor-pointer">
              <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-full blur opacity-40 group-hover:opacity-100 group-hover:blur-md transition duration-500" />
              <img 
                src="/nexoraLogo.png" 
                alt="Ujjwal Saini" 
                className="w-20 h-20 rounded-full border border-slate-950 bg-slate-950/90 p-2.5 object-contain relative z-10 transition-transform duration-500 group-hover:scale-105"
              />
            </div>
            
            <div className="space-y-1">
              <h2 className="text-xl font-extrabold text-white tracking-wide transition-all duration-300 group-hover:text-indigo-400">
                Ujjwal Saini
              </h2>
              <p className="text-xs text-indigo-400 font-semibold tracking-wider uppercase">Lead Architect & Developer</p>
              <div className="flex items-center justify-center gap-1.5 text-[10px] text-slate-500 font-mono">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
                <span>Delhi, India</span>
              </div>
            </div>

            <p className="text-xs text-slate-300/90 leading-relaxed text-center px-2">
              When not tuning low-latency Redis locks or optimizing LLM payload paths, Ujjwal crafts high-performance web systems and designs responsive glassmorphic interfaces.
            </p>

            {/* Creative Philosophy Quote */}
            <div className="border-y border-white/5 py-3 w-full">
              <p className="text-[11px] italic text-indigo-300/80 leading-relaxed font-serif">
                "Good architecture is invisible. It feels like magic but runs on pure determinism."
              </p>
            </div>

            {/* Creative Stats Grid */}
            <div className="grid grid-cols-3 gap-2 w-full text-center">
              <div className="rounded-lg bg-slate-950/60 p-2 border border-white/[0.03] hover:border-indigo-500/10 transition-all duration-350">
                <span className="text-[14px] font-extrabold text-white block">99.8%</span>
                <span className="text-[9px] text-slate-500 block uppercase font-mono tracking-wider">Squash Rate</span>
              </div>
              <div className="rounded-lg bg-slate-950/60 p-2 border border-white/[0.03] hover:border-indigo-500/10 transition-all duration-350">
                <span className="text-[14px] font-extrabold text-white block">&lt;200ms</span>
                <span className="text-[9px] text-slate-500 block uppercase font-mono tracking-wider">Latency</span>
              </div>
              <div className="rounded-lg bg-slate-950/60 p-2 border border-white/[0.03] hover:border-indigo-500/10 transition-all duration-350">
                <span className="text-[14px] font-extrabold text-white block">Infinite</span>
                <span className="text-[9px] text-slate-500 block uppercase font-mono tracking-wider">Passion</span>
              </div>
            </div>

            {/* Core Expertise Tags */}
            <div className="flex flex-wrap justify-center gap-1.5 max-w-xs">
              {["FastAPI", "Redis Cache", "MongoDB", "Groq API", "Next.js", "Tailwind CSS", "Docker"].map((tech) => (
                <span key={tech} className="text-[9px] font-mono px-2 py-0.5 rounded border border-white/5 bg-white/5 text-slate-400 transition-colors duration-300 group-hover:border-indigo-500/10 group-hover:bg-indigo-500/5 group-hover:text-indigo-400">
                  {tech}
                </span>
              ))}
            </div>

            {/* Premium Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 w-full pt-2">
              <a 
                href="https://github.com/UjjwalSaini07" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="flex-1 py-2 rounded-lg border border-white/5 bg-white/5 text-xs font-semibold text-white text-center hover:bg-white/10 hover:border-white/10 transition-all duration-300 shadow-md"
              >
                GitHub
              </a>
              <a 
                href="https://ujjwalsaini.vercel.app" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="flex-1 py-2 rounded-lg border border-indigo-500/25 bg-indigo-500/10 text-xs font-semibold text-indigo-400 text-center hover:bg-indigo-500/20 hover:border-indigo-500/45 transition-all duration-300 shadow-[0_0_15px_rgba(99,102,241,0.15)]"
              >
                Portfolio
              </a>
            </div>
          </div>
        </div>

        {/* Unique Interactive Chat Q&A with Lead Architect Ujjwal */}
        <div className="lg:col-span-2 rounded-2xl border border-indigo-500/10 bg-slate-950/20 backdrop-blur-md p-6 md:p-8 flex flex-col justify-between shadow-xl relative overflow-hidden">
          <div className="absolute inset-0 bg-indigo-500/[0.01] pointer-events-none" />
          
          <div className="space-y-6 z-10">
            <div>
              <span className="text-xs font-mono tracking-wider text-indigo-400 uppercase">Q&A CONSOLE</span>
              <h2 className="text-xl font-bold text-white mt-1">Interview the Lead Architect</h2>
              <p className="text-xs text-slate-400 mt-1">
                Select a topic below to interact with Ujjwal's engineering decision engine.
              </p>
            </div>

            {/* Question Selector Buttons */}
            <div className="flex flex-wrap gap-2.5">
              {Object.keys(INTERVIEW_TURNS).map((topic) => (
                <button
                  key={topic}
                  onClick={() => setSelectedTopic(topic)}
                  className={`text-xs font-semibold px-4 py-2.5 rounded-xl border transition-all duration-300 ${
                    selectedTopic === topic
                      ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-400 shadow-[0_4px_15px_rgba(99,102,241,0.15)]"
                      : "bg-slate-950/40 border-white/5 text-slate-400 hover:border-white/10 hover:bg-slate-950/60"
                  }`}
                >
                  ❓ {INTERVIEW_TURNS[topic].question}
                </button>
              ))}
            </div>

            {/* Stylized Architect Reply Bubble */}
            <div className="rounded-xl border border-white/5 bg-slate-950/40 p-5 space-y-3 min-h-[140px] flex flex-col justify-center">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-indigo-400 animate-pulse" />
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Ujjwal's Response</span>
              </div>
              
              {isTyping ? (
                <div className="flex items-center gap-1.5 py-2">
                  <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              ) : (
                <p className="text-xs text-slate-300 leading-relaxed font-mono">
                  {displayedAnswer}
                </p>
              )}
            </div>
          </div>

          {/* Bottom Card Footer */}
          <div className="pt-4 border-t border-white/5 flex items-center justify-between text-[10px] text-slate-500 font-mono z-10">
            <span>AUDITING AGENT PORTFOLIO METRICS</span>
            <a 
              href="https://ujjwalsaini.vercel.app" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-indigo-400 hover:underline hover:text-indigo-300 transition-colors"
            >
              Explore Live Projects &rarr;
            </a>
          </div>

        </div>
      </div>

      {/* Interactive Engine A: Priority Score Calculator */}
      <div className="rounded-2xl border border-indigo-500/10 bg-slate-950/20 backdrop-blur-md p-6 md:p-8 space-y-8 shadow-xl">
        <div>
          <span className="text-xs font-mono tracking-wider text-indigo-400 uppercase">ENGINE SIMULATOR</span>
          <h2 className="text-xl font-bold text-white mt-1">Interactive Priority Score Calculator</h2>
          <p className="text-xs text-slate-400 mt-1">
            Prioritizes active triggers deterministically using a 0-100 scoring model before invoking LLM pipelines.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Controls */}
          <div className="lg:col-span-3 space-y-5">
            {/* Urgency */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <label className="text-slate-300 font-medium">Urgency Rating (1-5)</label>
                <span className="font-mono text-indigo-400 font-bold">{urgency}</span>
              </div>
              <input 
                type="range" min="1" max="5" value={urgency} 
                onChange={(e) => setUrgency(parseInt(e.target.value))}
                className="w-full h-1 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>

            {/* Expiry Hours */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <label className="text-slate-300 font-medium">Hours Until Expiration</label>
                <span className="font-mono text-indigo-400 font-bold">{expiryHours}h</span>
              </div>
              <input 
                type="range" min="1" max="200" value={expiryHours} 
                onChange={(e) => setExpiryHours(parseInt(e.target.value))}
                className="w-full h-1 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>

            {/* Trigger Kind dropdown */}
            <div className="space-y-2">
              <label className="text-xs text-slate-300 font-medium block">Trigger Kind / Business Value</label>
              <select 
                value={triggerKind}
                onChange={(e) => setTriggerKind(e.target.value)}
                className="w-full rounded-lg border border-white/5 bg-slate-950 p-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
              >
                {Object.keys(KIND_WEIGHTS).map((kind) => (
                  <option key={kind} value={kind}>{kind} (Weight: {KIND_WEIGHTS[kind]})</option>
                ))}
              </select>
            </div>

            {/* Source & Scope Row */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <span className="text-xs text-slate-300 font-medium block">Trigger Source</span>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setSource("internal")}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                      source === "internal" ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-400" : "bg-slate-950 border-white/5 text-slate-400"
                    }`}
                  >
                    Internal
                  </button>
                  <button 
                    onClick={() => setSource("external")}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                      source === "external" ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-400" : "bg-slate-950 border-white/5 text-slate-400"
                    }`}
                  >
                    External
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <span className="text-xs text-slate-300 font-medium block">Target Scope</span>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setScope("merchant")}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                      scope === "merchant" ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-400" : "bg-slate-950 border-white/5 text-slate-400"
                    }`}
                  >
                    Merchant
                  </button>
                  <button 
                    onClick={() => setScope("customer")}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                      scope === "customer" ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-400" : "bg-slate-950 border-white/5 text-slate-400"
                    }`}
                  >
                    Customer
                  </button>
                </div>
              </div>
            </div>

            {/* Payload Keys */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <label className="text-slate-300 font-medium">Payload Keys count</label>
                <span className="font-mono text-indigo-400 font-bold">{payloadKeys}</span>
              </div>
              <input 
                type="range" min="0" max="10" value={payloadKeys} 
                onChange={(e) => setPayloadKeys(parseInt(e.target.value))}
                className="w-full h-1 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>
          </div>

          {/* Real-time Math Score Box */}
          <div className="lg:col-span-2 rounded-xl border border-indigo-500/10 bg-slate-950/60 p-6 flex flex-col justify-between shadow-2xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent pointer-events-none" />
            
            <div className="space-y-4 relative z-10">
              <span className="text-[10px] font-mono tracking-widest text-slate-500 uppercase">PRIORITY RATING</span>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-extrabold text-white tracking-tight">{totalPriorityScore}</span>
                <span className="text-sm text-slate-500">/ 100</span>
              </div>
              
              {/* Score bar */}
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                <div 
                  className="bg-indigo-500 h-2 rounded-full transition-all duration-500 shadow-[0_0_12px_rgba(99,102,241,0.5)]" 
                  style={{ width: `${totalPriorityScore}%` }}
                />
              </div>
            </div>

            {/* Scoring breakdown parameters */}
            <div className="space-y-3 pt-6 border-t border-white/5 text-xs relative z-10">
              <div className="flex justify-between">
                <span className="text-slate-400">Urgency rating ({urgency} × 5):</span>
                <span className="font-mono text-white">+{urgencyPts} pts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Expiry proximity ({expiryHours}h left):</span>
                <span className="font-mono text-white">+{expiryPts} pts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Kind weight ({triggerKind}):</span>
                <span className="font-mono text-white">+{kindPts} pts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Source weight ({source}):</span>
                <span className="font-mono text-white">+{sourcePts} pts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Scope weight ({scope}):</span>
                <span className="font-mono text-white">+{scopePts} pts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Payload richness ({payloadKeys} keys):</span>
                <span className="font-mono text-white">+{payloadPts} pts</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
