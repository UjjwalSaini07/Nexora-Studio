// frontend/app/scores/page.tsx
"use client";

import { useMemo } from "react";
import { api, type ActionLogEntry } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Card, MetricStat, Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";

/**
 * NOTE on scope: the actual 5-dimension judge score (specificity, category
 * fit, merchant fit, decision quality, engagement compulsion) is produced
 * by magicpin's own LLM judge during a real test run — this dashboard has
 * no access to that scoring model. What it CAN show, from data the bot
 * itself logs, is the set of objective anti-patterns the rubric explicitly
 * penalizes (URLs, repeats, taboo vocabulary, missing required fields) plus
 * basic specificity proxies (numeric content, message length). Labelled
 * accordingly rather than presented as a real score.
 */

const URL_PATTERN = /https?:\/\//i;
const NUMBER_PATTERN = /\d/g;

function analyzeAction(a: ActionLogEntry) {
  return {
    hasUrl: URL_PATTERN.test(a.body),
    hasTabooHit: (a.taboo_hits?.length ?? 0) > 0,
    numberCount: (a.body.match(NUMBER_PATTERN) ?? []).length,
    bodyLength: a.body.length,
    hasRationale: a.rationale.trim().length > 0,
    hasSuppressionKey: a.suppression_key.trim().length > 0,
  };
}

export default function ScoresPage() {
  const actionsPoll = usePolling(() => api.recentActions(200), 8000);

  const analysis = useMemo(() => {
    const actions = actionsPoll.data?.actions ?? [];
    const analyzed = actions.map((a) => ({ action: a, ...analyzeAction(a) }));

    const byTemplate = new Map<string, { count: number; avgNumbers: number; urlHits: number; tabooHits: number }>();
    for (const a of analyzed) {
      const entry = byTemplate.get(a.action.template_name) ?? { count: 0, avgNumbers: 0, urlHits: 0, tabooHits: 0 };
      entry.count += 1;
      entry.avgNumbers += a.numberCount;
      entry.urlHits += a.hasUrl ? 1 : 0;
      entry.tabooHits += a.hasTabooHit ? 1 : 0;
      byTemplate.set(a.action.template_name, entry);
    }
    for (const [, entry] of byTemplate) {
      entry.avgNumbers = entry.count > 0 ? entry.avgNumbers / entry.count : 0;
    }

    return {
      total: analyzed.length,
      urlViolations: analyzed.filter((a) => a.hasUrl).length,
      tabooViolations: analyzed.filter((a) => a.hasTabooHit).length,
      missingRationale: analyzed.filter((a) => !a.hasRationale).length,
      missingSuppressionKey: analyzed.filter((a) => !a.hasSuppressionKey).length,
      avgNumbersPerMessage:
        analyzed.length > 0 ? analyzed.reduce((s, a) => s + a.numberCount, 0) / analyzed.length : 0,
      byTemplate: Array.from(byTemplate.entries()).sort((a, b) => b[1].count - a[1].count),
    };
  }, [actionsPoll.data]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-vera-text-bright">Score analytics</h1>
        <p className="text-sm text-vera-muted mt-1">
          Objective anti-pattern tracking from the bot&apos;s own action log. The real 5-dimension judge
          score is produced by magicpin&apos;s LLM judge during a test run — not reproduced here.
        </p>
      </div>

      {actionsPoll.loading && !actionsPoll.data ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : actionsPoll.error && !actionsPoll.data ? (
        <ErrorState message={actionsPoll.error} />
      ) : analysis.total === 0 ? (
        <Card>
          <EmptyState
            title="No actions logged yet"
            hint="Run a tick with real triggers pushed to see anti-pattern tracking here."
          />
        </Card>
      ) : (
        <>
          <Card title="Anti-pattern tracker">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
              <MetricStat label="Actions analyzed" value={analysis.total} />
              <MetricStat
                label="URL violations"
                value={analysis.urlViolations}
                tone={analysis.urlViolations > 0 ? "danger" : "success"}
              />
              <MetricStat
                label="Taboo word hits"
                value={analysis.tabooViolations}
                tone={analysis.tabooViolations > 0 ? "warn" : "success"}
              />
              <MetricStat
                label="Missing rationale"
                value={analysis.missingRationale}
                tone={analysis.missingRationale > 0 ? "danger" : "success"}
              />
              <MetricStat
                label="Avg numbers/msg"
                value={analysis.avgNumbersPerMessage.toFixed(1)}
                tone={analysis.avgNumbersPerMessage >= 1 ? "success" : "warn"}
              />
            </div>
          </Card>

          <Card title="Breakdown by trigger template">
            <div className="flex flex-col gap-3">
              {analysis.byTemplate.map(([name, stats]) => (
                <div
                  key={name}
                  className="flex items-center justify-between gap-4 py-2 border-b border-vera-border last:border-0"
                >
                  <span className="text-sm font-mono text-vera-text truncate">{name}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <Badge>{stats.count} sent</Badge>
                    <Badge tone={stats.avgNumbers >= 1 ? "success" : "warn"}>
                      {stats.avgNumbers.toFixed(1)} nums/msg
                    </Badge>
                    {stats.urlHits > 0 && <Badge tone="danger">{stats.urlHits} URL hits</Badge>}
                    {stats.tabooHits > 0 && <Badge tone="warn">{stats.tabooHits} taboo hits</Badge>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
