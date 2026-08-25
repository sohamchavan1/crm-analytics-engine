"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Loader2,
  AlertTriangle,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Info,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { compareReports, getComparisonDownloadUrl, type ComparisonResult } from "@/lib/api";

export default function ComparePage() {
  const searchParams = useSearchParams();
  const runIdA = searchParams.get("a") || "";
  const runIdB = searchParams.get("b") || "";

  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runIdA || !runIdB) {
      setError("Two report IDs are required for comparison.");
      setLoading(false);
      return;
    }
    compareReports(runIdA, runIdB)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : "Comparison failed"))
      .finally(() => setLoading(false));
  }, [runIdA, runIdB]);

  if (loading) {
    return (
      <div className="p-6 max-w-[900px] mx-auto flex flex-col items-center justify-center py-24">
        <Loader2 className="h-6 w-6 text-primary animate-spin mb-3" />
        <p className="text-sm font-medium">Generating comparison...</p>
        <p className="text-2xs text-muted-foreground mt-1">AI is analyzing both reports</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="p-6 max-w-[900px] mx-auto text-center py-16">
        <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">{error || "Comparison failed"}</p>
        <Link href="/reports">
          <Button variant="outline" size="sm" className="mt-3">Back to Reports</Button>
        </Link>
      </div>
    );
  }

  const { run_a, run_b, comparison } = result;
  const delta = comparison.metrics_delta;

  return (
    <div className="p-6 max-w-[900px] mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/reports">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-semibold">Report Comparison</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              {run_a.company} · {run_a.vertical_code}
            </p>
          </div>
        </div>
        <a href={getComparisonDownloadUrl(result.comparison_id)}>
          <Button size="sm" variant="outline">
            <Download className="h-3.5 w-3.5 mr-1.5" />
            DOCX
          </Button>
        </a>
      </div>

      {/* Period cards */}
      <div className="grid grid-cols-2 gap-3">
        <PeriodCard label="Period A (Older)" run={run_a} />
        <PeriodCard label="Period B (Newer)" run={run_b} />
      </div>

      {/* Executive comparison summary */}
      <div className="rounded-md border border-border p-4">
        <p className="text-2xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          AI Comparison Summary
        </p>
        <p className="text-sm leading-relaxed">{comparison.summary}</p>
      </div>

      {/* Context note */}
      {comparison.context_note && (
        <div className="flex items-start gap-2 rounded-md bg-secondary/50 border border-border px-3 py-2.5">
          <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground">{comparison.context_note}</p>
        </div>
      )}

      {/* Metrics delta */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Key Metrics Change
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <DeltaCard label="CTR" value={delta.ctr_change} suffix="pp" />
          <DeltaCard label="CTOR" value={delta.ctor_change} suffix="pp" />
          <DeltaCard label="Conversions" value={delta.conversion_change} suffix="" isAbsolute />
          <DeltaCard label="Volume" value={delta.sent_change} suffix="" isAbsolute />
          <DeltaCard label="Delivery" value={delta.delivery_rate_change} suffix="pp" />
        </div>
      </div>

      {/* Improvements & Declines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {comparison.improvements.length > 0 && (
          <div className="rounded-md border border-emerald-100 bg-emerald-50/30 p-4 space-y-2">
            <p className="text-xs font-medium text-emerald-700 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingUp className="h-3 w-3" /> Improvements
            </p>
            <ul className="space-y-1.5">
              {comparison.improvements.map((item, i) => (
                <li key={i} className="text-xs text-emerald-900 flex items-start gap-2">
                  <ArrowUpRight className="h-3 w-3 text-emerald-500 mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {comparison.declines.length > 0 && (
          <div className="rounded-md border border-red-100 bg-red-50/30 p-4 space-y-2">
            <p className="text-xs font-medium text-red-700 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingDown className="h-3 w-3" /> Declines
            </p>
            <ul className="space-y-1.5">
              {comparison.declines.map((item, i) => (
                <li key={i} className="text-xs text-red-900 flex items-start gap-2">
                  <ArrowDownRight className="h-3 w-3 text-red-500 mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Strategy Shifts */}
      {comparison.strategy_shifts.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Strategy Shifts
          </p>
          <div className="space-y-1.5">
            {comparison.strategy_shifts.map((shift, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border border-border px-3 py-2.5">
                <ArrowRight className="h-3 w-3 text-primary mt-0.5 shrink-0" />
                <p className="text-xs">{shift}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendation */}
      <div className="rounded-md border border-primary/20 bg-primary/5 p-4">
        <p className="text-2xs font-medium text-primary/70 uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <Lightbulb className="h-3 w-3" /> Recommendation
        </p>
        <p className="text-sm leading-relaxed">{comparison.recommendation}</p>
      </div>

      {/* Links to individual reports */}
      <div className="flex gap-2 pt-2">
        <Link href={`/reports/${run_a.run_id}`}>
          <Button variant="outline" size="sm">View Period A</Button>
        </Link>
        <Link href={`/reports/${run_b.run_id}`}>
          <Button variant="outline" size="sm">View Period B</Button>
        </Link>
      </div>
    </div>
  );
}

/* ---------- Sub-components ---------- */

function PeriodCard({ label, run }: {
  label: string;
  run: ComparisonResult["run_a"];
}) {
  return (
    <div className="rounded-md border border-border px-4 py-3">
      <p className="text-2xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">{label}</p>
      <p className="text-xs text-foreground">
        {run.date_range_start && run.date_range_end
          ? `${run.date_range_start} — ${run.date_range_end}`
          : "Date range unavailable"}
      </p>
      <div className="flex items-center gap-3 mt-1 text-2xs text-muted-foreground">
        <span>{run.campaign_count} campaigns</span>
        <span>{run.channels.join(", ") || "—"}</span>
      </div>
      <div className="flex items-center gap-3 mt-2 text-xs tabular-nums">
        <span>CTR <strong>{run.overall.overall_ctr ?? "—"}%</strong></span>
        <span>CTOR <strong>{run.overall.overall_ctor ?? "—"}%</strong></span>
      </div>
    </div>
  );
}

function DeltaCard({ label, value, suffix, isAbsolute }: {
  label: string;
  value: number;
  suffix: string;
  isAbsolute?: boolean;
}) {
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const display = isAbsolute
    ? `${isPositive ? "+" : ""}${formatNumber(value)}`
    : `${isPositive ? "+" : ""}${value.toFixed(1)}${suffix}`;

  return (
    <div className="rounded-md border border-border px-3 py-2.5 text-center">
      <p className="text-2xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${
        isNeutral ? "text-muted-foreground" : isPositive ? "text-emerald-600" : "text-red-600"
      }`}>
        {isNeutral ? (
          <span className="flex items-center justify-center gap-1"><Minus className="h-3 w-3" /> 0</span>
        ) : (
          display
        )}
      </p>
    </div>
  );
}

function formatNumber(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
