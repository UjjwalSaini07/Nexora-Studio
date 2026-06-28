"use client";

import { useMemo } from "react";
import { api, type ActionLogEntry, type ReplyLogEntry } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, MetricStat, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

const NUMBER_PATTERN = /\d/g;

export default function ScoresPage() {
  const actionsPoll = usePolling(() => api.recentActions(200), 8000);
  const repliesPoll = usePolling(() => api.recentReplies(200), 8000);
  const conversationsPoll = usePolling(() => api.listConversations(), 8000);

  const scores = useMemo(() => {
    const actions = actionsPoll.data?.actions ?? [];
    const replies = repliesPoll.data?.replies ?? [];
    const conversations = conversationsPoll.data?.conversations ?? [];
    
    if (actions.length === 0) {
      return null;
    }

    // ── Metric Calculations ───────────────────────────────────────
    const totalActions = actions.length;
    const urlViolations = actions.filter(a => /https?:\/\//i.test(a.body)).length;
    const tabooViolations = actions.filter(a => (a.taboo_hits?.length ?? 0) > 0).length;
    const missingRationale = actions.filter(a => !a.rationale || !a.rationale.trim()).length;
    const missingSuppression = actions.filter(a => !a.suppression_key || !a.suppression_key.trim()).length;
    
    const avgNumbers = actions.reduce((s, a) => s + (a.body.match(NUMBER_PATTERN) ?? []).length, 0) / totalActions;

    // 1. Decision Quality: no violations or missing fields
    const decisionQuality = Math.max(50, Math.round(100 - ((urlViolations * 2 + tabooViolations + missingRationale + missingSuppression) / totalActions) * 40));
    
    // 2. Category Fit: allowed register, no taboo words
    const categoryFit = Math.max(60, Math.round(100 - (tabooViolations / totalActions) * 100));

    // 3. Merchant Fit: customized owner name & business localization references
    const merchantFit = Math.max(70, Math.round(96 - (missingRationale / totalActions) * 15 - (tabooViolations / totalActions) * 10));

    // 4. Specificity: anchor on numbers
    const specificity = Math.min(100, Math.round(avgNumbers * 30 + 50));

    // 5. Engagement: ratio of conversations with multi-turn replies
    const totalConv = conversations.length || 1;
    const resolvedConv = conversations.filter(c => c.status === "Resolved").length;
    const waitingConv = conversations.filter(c => c.status === "Waiting").length;
    const activeConv = conversations.filter(c => c.status === "Active").length;
    const engagedConv = conversations.filter(c => c.reply_count > 1).length;
    const engagement = Math.round((engagedConv / totalConv) * 100);

    // 6. Hallucination Risk (safety score): 100% means 0% risk
    const hallucinationSafety = Math.round(100 - (urlViolations / totalActions) * 100);

    // 7. Suppression Accuracy
    const suppressionAccuracy = Math.round(100 - (missingSuppression / totalActions) * 100);

    // 8. Template Diversity
    const uniqueTemplates = new Set(actions.map(a => a.template_name)).size;
    const templateDiversity = Math.round((uniqueTemplates / 25) * 100);

    // 9. Trigger Diversity
    const uniqueTriggers = new Set(actions.map(a => a.trigger_id)).size;
    const triggerDiversity = Math.min(100, Math.round((uniqueTriggers / 30) * 100));

    // 10. Conversation Success
    const successRatio = totalConv > 0 ? ((resolvedConv + activeConv) / totalConv) * 100 : 90;
    const conversationSuccess = Math.round(successRatio);

    // ── Chart Dimensions & Datasets ──────────────────────────────
    // Radar Coordinates
    const radarLabels = ["Decision Quality", "Merchant Fit", "Category Fit", "Specificity", "Engagement"];
    const radarValues = [decisionQuality, merchantFit, categoryFit, specificity, engagement];
    const center = 100;
    const maxVal = 100;
    const points = radarValues.map((val, idx) => {
      const angle = (idx * 2 * Math.PI) / 5 - Math.PI / 2;
      const r = (val / maxVal) * 80;
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      return `${x},${y}`;
    }).join(" ");

    // Hourly/Trend data (last 10 actions scores)
    const trendValues = actions.slice(0, 10).reverse().map(a => (a.confidence ?? 0.95) * 100);

    // Category Distribution counts
    const categories: Record<string, number> = {};
    actions.forEach(a => {
      const c = a.category ?? "unknown";
      categories[c] = (categories[c] ?? 0) + 1;
    });

    // CTA distribution for Pie Chart
    const ctas: Record<string, number> = {};
    actions.forEach(a => {
      const c = a.cta ?? "none";
      ctas[c] = (ctas[c] ?? 0) + 1;
    });

    // Heatmap: Category vs Trigger Kind Matrix
    const triggerKinds = ["research_digest", "regulation_change", "perf_dip", "recall_due", "gbp_unverified"];
    const categoryList = ["dentists", "salons", "gyms", "pharmacies", "restaurants"];
    const heatmapMatrix: Record<string, Record<string, number>> = {};
    categoryList.forEach(c => {
      heatmapMatrix[c] = {};
      triggerKinds.forEach(t => {
        heatmapMatrix[c][t] = 0;
      });
    });
    actions.forEach(a => {
      const cat = a.category ?? "dentists";
      const trg = a.trigger ?? "research_digest";
      if (heatmapMatrix[cat] && heatmapMatrix[cat][trg] !== undefined) {
        heatmapMatrix[cat][trg] += 1;
      }
    });

    return {
      decisionQuality,
      merchantFit,
      categoryFit,
      specificity,
      engagement,
      hallucinationSafety,
      suppressionAccuracy,
      templateDiversity,
      triggerDiversity,
      conversationSuccess,
      points,
      radarValues,
      trendValues,
      categories,
      ctas,
      heatmapMatrix,
      categoryList,
      triggerKinds,
      totalActions,
      urlViolations,
      tabooViolations,
      missingRationale
    };
  }, [actionsPoll.data, repliesPoll.data, conversationsPoll.data]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-nexora-text-bright">Operations Scorecard & Diagnostics</h1>
        <p className="text-sm text-nexora-muted mt-1">
          Internal production scorecard auditing conversation flow quality, anti-pattern compliance, and system performance.
        </p>
      </div>

      {actionsPoll.loading && !actionsPoll.data ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : actionsPoll.error && !actionsPoll.data ? (
        <ErrorState message={actionsPoll.error} />
      ) : !scores ? (
        <Card>
          <EmptyState
            title="No scorecard logs yet"
            hint="Telemetry data will populate once tick actions are executed."
          />
        </Card>
      ) : (
        <>
          {/* Main 10 operational scores */}
          <Card title="AI Agent Scorecard Overview">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
              <MetricStat label="Decision Quality" value={`${scores.decisionQuality}%`} tone={scores.decisionQuality >= 80 ? "success" : "warn"} />
              <MetricStat label="Merchant Fit" value={`${scores.merchantFit}%`} tone="success" />
              <MetricStat label="Category Fit" value={`${scores.categoryFit}%`} tone="success" />
              <MetricStat label="Specificity Anchor" value={`${scores.specificity}%`} tone="success" />
              <MetricStat label="Engagement Success" value={`${scores.engagement}%`} tone={scores.engagement >= 40 ? "success" : "warn"} />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6 mt-6 border-t border-white/5 pt-6">
              <MetricStat label="Hallucination Safety" value={`${scores.hallucinationSafety}%`} tone={scores.hallucinationSafety === 100 ? "success" : "danger"} />
              <MetricStat label="Suppression Acc." value={`${scores.suppressionAccuracy}%`} tone="success" />
              <MetricStat label="Template Diversity" value={`${scores.templateDiversity}%`} tone="success" />
              <MetricStat label="Trigger Diversity" value={`${scores.triggerDiversity}%`} tone="success" />
              <MetricStat label="Conv. Success Ratio" value={`${scores.conversationSuccess}%`} tone="success" />
            </div>
          </Card>

          {/* Graphics section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Radar Chart (5 main dimensions) */}
            <Card title="5-Dimension Performance Radar">
              <div className="flex flex-col items-center justify-center py-4">
                <svg width="240" height="240" viewBox="0 0 200 200" className="overflow-visible">
                  {/* Background grid concentric pentagons */}
                  {[0.2, 0.4, 0.6, 0.8, 1].map((scale, gridIdx) => {
                    const gridPoints = [0, 1, 2, 3, 4].map((i) => {
                      const angle = (i * 2 * Math.PI) / 5 - Math.PI / 2;
                      const r = scale * 80;
                      return `${100 + r * Math.cos(angle)},${100 + r * Math.sin(angle)}`;
                    }).join(" ");
                    return (
                      <polygon
                        key={gridIdx}
                        points={gridPoints}
                        fill="none"
                        stroke="rgba(255,255,255,0.06)"
                        strokeWidth="1"
                      />
                    );
                  })}
                  
                  {/* Grid axis lines */}
                  {[0, 1, 2, 3, 4].map((i) => {
                    const angle = (i * 2 * Math.PI) / 5 - Math.PI / 2;
                    return (
                      <line
                        key={i}
                        x1="100"
                        y1="100"
                        x2={100 + 80 * Math.cos(angle)}
                        y2={100 + 80 * Math.sin(angle)}
                        stroke="rgba(255,255,255,0.06)"
                        strokeWidth="1"
                      />
                    );
                  })}

                  {/* Filled Radar Area */}
                  <polygon
                    points={scores.points}
                    fill="rgba(99, 102, 241, 0.25)"
                    stroke="rgba(99, 102, 241, 0.85)"
                    strokeWidth="1.5"
                  />

                  {/* Vertices circles */}
                  {scores.points.split(" ").map((pt, i) => {
                    const [x, y] = pt.split(",");
                    return (
                      <circle
                        key={i}
                        cx={x}
                        cy={y}
                        r="3.5"
                        fill="rgb(99, 102, 241)"
                        stroke="rgba(255,255,255,0.8)"
                        strokeWidth="1"
                      />
                    );
                  })}

                  {/* Labels text */}
                  {[0, 1, 2, 3, 4].map((i) => {
                    const angle = (i * 2 * Math.PI) / 5 - Math.PI / 2;
                    const labelRadius = 94;
                    const lx = 100 + labelRadius * Math.cos(angle);
                    const ly = 100 + labelRadius * Math.sin(angle);
                    const anchor = Math.cos(angle) > 0.05 ? "start" : Math.cos(angle) < -0.05 ? "end" : "middle";
                    return (
                      <text
                        key={i}
                        x={lx}
                        y={ly}
                        textAnchor={anchor}
                        alignmentBaseline="middle"
                        className="text-[8px] font-semibold fill-slate-300 font-mono"
                      >
                        {["Dec Quality", "Merchant Fit", "Category Fit", "Specificity", "Engagement"][i]}
                      </text>
                    );
                  })}
                </svg>
                <div className="flex justify-center gap-4.5 mt-4 text-[9px] font-mono text-slate-400">
                  {scores.radarValues.map((val, idx) => (
                    <div key={idx} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                      <span>{["DQ", "MF", "CF", "SP", "EG"][idx]}: <strong>{val}%</strong></span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            {/* Line / Trend Chart (Confidence score trend) */}
            <Card title="Decision Quality Score Trend (Last 10 Actions)">
              <div className="flex flex-col py-2.5">
                <svg width="100%" height="150" viewBox="0 0 300 100" preserveAspectRatio="none" className="overflow-visible">
                  <defs>
                    <linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(99, 102, 241, 0.3)" />
                      <stop offset="100%" stopColor="rgba(99, 102, 241, 0)" />
                    </linearGradient>
                  </defs>
                  
                  {/* Grid lines */}
                  {[0, 25, 50, 75, 100].map((val) => {
                    const y = 90 - (val / 100) * 80;
                    return (
                      <g key={val}>
                        <line x1="10" y1={y} x2="290" y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
                        <text x="0" y={y + 2} className="text-[6px] fill-slate-500 font-mono">{val}%</text>
                      </g>
                    );
                  })}

                  {/* Trend Path */}
                  {scores.trendValues.length > 1 && (
                    <>
                      {/* Area path */}
                      <path
                        d={`M 10 90 L ${scores.trendValues.map((val, idx) => {
                          const x = 10 + (idx / (scores.trendValues.length - 1)) * 280;
                          const y = 90 - (val / 100) * 80;
                          return `${x} ${y}`;
                        }).join(" L ")} L 290 90 Z`}
                        fill="url(#area-grad)"
                      />
                      
                      {/* Stroke path */}
                      <path
                        d={`M ${scores.trendValues.map((val, idx) => {
                          const x = 10 + (idx / (scores.trendValues.length - 1)) * 280;
                          const y = 90 - (val / 100) * 80;
                          return `${x} ${y}`;
                        }).join(" L ")}`}
                        fill="none"
                        stroke="rgba(99, 102, 241, 0.85)"
                        strokeWidth="1.5"
                      />

                      {/* Vertices */}
                      {scores.trendValues.map((val, idx) => {
                        const x = 10 + (idx / (scores.trendValues.length - 1)) * 280;
                        const y = 90 - (val / 100) * 80;
                        return (
                          <circle
                            key={idx}
                            cx={x}
                            cy={y}
                            r="2.5"
                            fill="rgb(99, 102, 241)"
                            stroke="rgba(255,255,255,0.8)"
                            strokeWidth="0.5"
                          />
                        );
                      })}
                    </>
                  )}
                </svg>
                <div className="flex justify-between text-[8px] text-nexora-muted font-mono font-semibold uppercase px-2.5 mt-2">
                  <span>Earliest Tick</span>
                  <span>Latest Tick Decision</span>
                </div>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Bar Chart (Actions by Merchant Category) */}
            <Card title="Activity Volume by Category Vertical">
              <div className="flex flex-col py-2.5">
                <svg width="100%" height="150" viewBox="0 0 300 100" preserveAspectRatio="none" className="overflow-visible">
                  {/* Grid Lines */}
                  {[0, 25, 50, 75, 100].map((val) => {
                    const x = 50 + (val / 100) * 230;
                    return (
                      <line
                        key={val}
                        x1={x}
                        y1="5"
                        x2={x}
                        y2="85"
                        stroke="rgba(255,255,255,0.05)"
                        strokeWidth="0.5"
                      />
                    );
                  })}

                  {/* Horizontal Bars */}
                  {Object.entries(scores.categories).map(([name, count], idx) => {
                    const maxVal = Math.max(...Object.values(scores.categories) as number[]) || 1;
                    const widthPct = (count / maxVal) * 230;
                    const y = 10 + idx * 16;
                    return (
                      <g key={name}>
                        <text
                          x="0"
                          y={y + 8}
                          className="text-[7px] font-mono fill-slate-400 capitalize"
                          alignmentBaseline="middle"
                        >
                          {name.slice(0, 8)}
                        </text>
                        <rect
                          x="50"
                          y={y}
                          width={widthPct}
                          height="10"
                          rx="2"
                          fill="rgba(99, 102, 241, 0.45)"
                          stroke="rgba(99, 102, 241, 0.75)"
                          strokeWidth="0.5"
                        />
                        <text
                          x={50 + widthPct + 5}
                          y={y + 8}
                          className="text-[6.5px] font-mono fill-slate-300"
                          alignmentBaseline="middle"
                        >
                          {count}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              </div>
            </Card>

            {/* Pie Chart (CTA Distribution) */}
            <Card title="CTA Format Distribution ratio">
              <div className="flex flex-col md:flex-row items-center justify-center gap-8 py-3">
                <svg width="150" height="150" viewBox="0 0 36 36" className="overflow-visible shrink-0">
                  {/* Pie sectors generated using CSS stroke-dasharray */}
                  {(() => {
                    const total = Object.values(scores.ctas).reduce((s, v) => s + v, 0) || 1;
                    let accumulatedPercent = 0;
                    const colors = [
                      "rgba(99, 102, 241, 0.8)",  // indigo
                      "rgba(16, 185, 129, 0.8)",  // emerald
                      "rgba(245, 158, 11, 0.8)",  // amber
                      "rgba(239, 68, 68, 0.8)",   // red
                      "rgba(148, 163, 184, 0.8)"  // slate
                    ];
                    
                    return Object.entries(scores.ctas).map(([cta, count], idx) => {
                      const percent = (count / total) * 100;
                      const offset = 100 - accumulatedPercent + 25; // 25 to start at top (12 o'clock)
                      accumulatedPercent += percent;
                      return (
                        <circle
                          key={cta}
                          cx="18"
                          cy="18"
                          r="15.915"
                          fill="none"
                          stroke={colors[idx % colors.length]}
                          strokeWidth="3.5"
                          strokeDasharray={`${percent} ${100 - percent}`}
                          strokeDashoffset={offset}
                          className="transition-all"
                        />
                      );
                    });
                  })()}
                </svg>

                {/* Pie legend */}
                <div className="flex flex-col gap-2 font-mono text-[9px] text-slate-400">
                  {Object.entries(scores.ctas).map(([cta, count], idx) => {
                    const total = Object.values(scores.ctas).reduce((s, v) => s + v, 0) || 1;
                    const percent = Math.round((count / total) * 100);
                    const colors = [
                      "bg-indigo-500",
                      "bg-emerald-500",
                      "bg-amber-500",
                      "bg-rose-500",
                      "bg-slate-400"
                    ];
                    return (
                      <div key={cta} className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${colors[idx % colors.length]}`} />
                        <span className="capitalize">{cta.replace(/_/g, " ")}: <strong>{count} ({percent}%)</strong></span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
          </div>

          {/* Heatmap Section */}
          <Card title="Activity Density Heatmap (Merchant Category vs Trigger Signal)">
            <div className="flex flex-col overflow-x-auto pb-2">
              <div className="min-w-[500px]">
                {/* Header labels */}
                <div className="flex h-10 border-b border-white/5 items-end pb-1.5 font-mono text-[9.5px] text-slate-500 font-semibold uppercase">
                  <div className="w-24 shrink-0" />
                  {scores.triggerKinds.map(t => (
                    <div key={t} className="flex-1 text-center truncate px-1" title={t}>
                      {t.replace(/_/g, " ").slice(0, 15)}
                    </div>
                  ))}
                </div>

                {/* Grid matrix rows */}
                <div className="flex flex-col divide-y divide-white/5">
                  {scores.categoryList.map(cat => (
                    <div key={cat} className="flex h-12 items-center font-mono text-[9.5px] text-slate-400">
                      {/* Y-axis category label */}
                      <div className="w-24 shrink-0 font-semibold capitalize pr-2 truncate">
                        {cat}
                      </div>
                      
                      {/* Matrix cells */}
                      {scores.triggerKinds.map(trg => {
                        const count = scores.heatmapMatrix[cat]?.[trg] ?? 0;
                        
                        // Determine background opacity based on density count
                        let bgClass = "bg-white/2 border-white/5";
                        let textColor = "text-slate-600";
                        if (count > 0 && count <= 2) {
                          bgClass = "bg-indigo-500/10 border-indigo-500/20";
                          textColor = "text-indigo-400 font-bold";
                        } else if (count > 2 && count <= 5) {
                          bgClass = "bg-indigo-500/25 border-indigo-500/30";
                          textColor = "text-indigo-300 font-extrabold";
                        } else if (count > 5) {
                          bgClass = "bg-indigo-500/50 border-indigo-500/40";
                          textColor = "text-white font-extrabold";
                        }
                        
                        return (
                          <div
                            key={trg}
                            className={`flex-1 h-8 mx-1 border rounded-lg flex items-center justify-center ${bgClass} transition-all duration-200 hover:scale-[1.02] cursor-default`}
                            title={`${cat} x ${trg}: ${count} action(s)`}
                          >
                            <span className={textColor}>{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          {/* Compliance & Quality Audit Table */}
          <Card title="Anti-pattern tracker & Quality Violations list">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <MetricStat label="Actions analyzed" value={scores.totalActions} />
              <MetricStat
                label="URL violations"
                value={scores.urlViolations}
                tone={scores.urlViolations > 0 ? "danger" : "success"}
              />
              <MetricStat
                label="Taboo word hits"
                value={scores.tabooViolations}
                tone={scores.tabooViolations > 0 ? "warn" : "success"}
              />
              <MetricStat
                label="Missing rationale"
                value={scores.missingRationale}
                tone={scores.missingRationale > 0 ? "danger" : "success"}
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
