"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Calendar,
  Hash,
  Radio,
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  Clock,
  MessageSquare,
  Award,
  AlertTriangle,
  Lightbulb,
  BarChart3,
  Send,
  MousePointerClick,
  Eye,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getReport, getDownloadUrl } from "@/lib/api";

interface RunData {
  run_id: string;
  company: string;
  vertical_code: string;
  status: string;
  source_platform: string;
  source_filename: string;
  campaign_count: number;
  channels: string[];
  date_range_start: string | null;
  date_range_end: string | null;
  report_path: string | null;
  created_at: string;
  completed_at: string | null;
}

interface Facts {
  meta: {
    company: string;
    vertical: string;
    date_range_start: string;
    date_range_end: string;
    campaign_count: number;
    channels: string[];
    total_sent: number;
  };
  overall: {
    total_campaigns: number;
    total_sent: number;
    total_delivered: number;
    total_viewed: number;
    total_clicked: number;
    total_click_conversions: number;
    total_influenced_conversions: number;
    overall_ctr: number;
    overall_ctor: number;
    overall_delivery_rate: number;
    overall_cvr_click: number;
    overall_cvr_influenced: number;
  };
  by_channel: BucketItem[];
  by_day: BucketItem[];
  by_hour: BucketItem[];
  by_opening_style: ClassificationItem[];
  by_tone: ClassificationItem[];
  by_cta_strength: ClassificationItem[];
  by_emoji_bucket: ClassificationItem[];
  by_keyword: KeywordItem[];
  by_message_length: ClassificationItem[];
  top_performers: Performer[];
  bottom_performers: Performer[];
}

interface BucketItem {
  bucket?: string;
  channel?: string;
  segment?: string;
  campaign_count: number;
  total_sent: number;
  total_clicked: number;
  total_influenced_conversions: number;
  ctr: number;
  ctor: number;
}

interface ClassificationItem {
  label: string;
  campaign_count: number;
  ctr: number;
  ctor: number;
  total_influenced_conversions: number;
}

interface KeywordItem {
  keyword: string;
  campaign_count: number;
  total_sent: number;
  total_clicked: number;
  total_influenced_conversions: number;
  ctr: number;
  ctor: number;
}

interface Performer {
  campaign_name: string;
  channel: string;
  segment: string;
  offer: string;
  ctr: number;
  ctor: number;
  click_conversions: number;
  influenced_conversions: number;
  sent: number;
  message: string;
  title: string;
}

interface Insights {
  executive_summary: string;
  channel_insights: unknown[];
  creative_insights: {
    opening_style_narrative?: string;
    tone_narrative?: string;
    cta_narrative?: string;
    emoji_narrative?: string;
    headline_quality_narrative?: string;
    message_length_narrative?: string;
  } | null;
  timing_insights: {
    best_days?: string;
    best_hours?: string;
  } | null;
  top_performer_analysis: string;
  bottom_performer_analysis: string;
  recommendations: {
    priority: number;
    action: string;
    expected_impact: string;
    rationale: string;
  }[];
  trend_commentary: string | null;
}

type Tab = "overview" | "creative" | "timing" | "performers" | "recommendations";

export default function ReportDetailPage() {
  const params = useParams();
  const runId = params.runId as string;

  const [run, setRun] = useState<RunData | null>(null);
  const [facts, setFacts] = useState<Facts | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  useEffect(() => {
    async function load() {
      try {
        const data = await getReport(runId);
        setRun(data.run as unknown as RunData);
        const [factsRes, insightsRes] = await Promise.allSettled([
          fetch(`/api/reports/${runId}/facts`).then((r) => r.ok ? r.json() : null),
          fetch(`/api/reports/${runId}/insights`).then((r) => r.ok ? r.json() : null),
        ]);
        if (factsRes.status === "fulfilled") setFacts(factsRes.value);
        if (insightsRes.status === "fulfilled") setInsights(insightsRes.value);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [runId]);

  if (loading) {
    return (
      <div className="p-6 max-w-[1100px] mx-auto">
        <div className="animate-pulse space-y-3">
          <div className="h-6 w-64 bg-secondary rounded" />
          <div className="h-24 bg-secondary rounded-md" />
          <div className="h-48 bg-secondary rounded-md" />
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-6 max-w-[1100px] mx-auto text-center py-16">
        <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">{error || "Report not found"}</p>
        <Link href="/reports">
          <Button variant="outline" size="sm" className="mt-3">Back</Button>
        </Link>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ElementType }[] = [
    { key: "overview", label: "Overview", icon: BarChart3 },
    { key: "creative", label: "Creative", icon: MessageSquare },
    { key: "timing", label: "Timing", icon: Clock },
    { key: "performers", label: "Performers", icon: Award },
    { key: "recommendations", label: "Actions", icon: Lightbulb },
  ];

  return (
    <div className="p-6 max-w-[1100px] mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/reports">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-semibold">
              {run.company} · {run.vertical_code}
            </h1>
            <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
              {run.date_range_start && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {run.date_range_start} — {run.date_range_end}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Hash className="h-3 w-3" />
                {run.campaign_count} campaigns
              </span>
              <span className="flex items-center gap-1">
                <Radio className="h-3 w-3" />
                {run.channels?.join(", ") || "—"}
              </span>
            </div>
          </div>
        </div>
        {run.status === "complete" && (
          <a href={getDownloadUrl(runId)}>
            <Button size="sm">
              <Download className="h-3.5 w-3.5 mr-1.5" />
              DOCX
            </Button>
          </a>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <tab.icon className="h-3.5 w-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "overview" && <OverviewTab facts={facts} insights={insights} />}
      {activeTab === "creative" && <CreativeTab facts={facts} insights={insights} />}
      {activeTab === "timing" && <TimingTab facts={facts} insights={insights} />}
      {activeTab === "performers" && <PerformersTab facts={facts} insights={insights} />}
      {activeTab === "recommendations" && <RecommendationsTab insights={insights} />}
    </div>
  );
}

/* ---------- Overview Tab ---------- */

function OverviewTab({ facts, insights }: { facts: Facts | null; insights: Insights | null }) {
  if (!facts) return <EmptyState message="No analytics data available" />;

  const metrics = [
    { label: "Sent", value: formatNumber(facts.overall.total_sent), icon: Send },
    { label: "Clicked", value: formatNumber(facts.overall.total_clicked), icon: MousePointerClick },
    { label: "CTR", value: `${facts.overall.overall_ctr}%`, icon: Target },
    { label: "CTOR", value: `${facts.overall.overall_ctor}%`, icon: Eye },
    { label: "Conversions", value: formatNumber(facts.overall.total_influenced_conversions), icon: Zap },
    { label: "Delivery", value: `${facts.overall.overall_delivery_rate}%`, icon: Users },
  ];

  return (
    <div className="space-y-4">
      {/* Executive Summary */}
      {insights?.executive_summary && (
        <div className="rounded-md border border-border p-4">
          <p className="text-2xs font-medium text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
            <Zap className="h-3 w-3" /> Executive Summary
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
            {insights.executive_summary}
          </p>
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-md border border-border px-3 py-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <m.icon className="h-3 w-3 text-muted-foreground" />
              <span className="text-2xs text-muted-foreground">{m.label}</span>
            </div>
            <p className="text-base font-semibold tabular-nums">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Channel Breakdown */}
      {facts.by_channel.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Channel Performance</p>
          <DataTable
            headers={["Channel", "Campaigns", "Sent", "CTR", "CTOR", "Conversions"]}
            rows={facts.by_channel.map((c) => [
              c.channel || c.bucket || c.segment || "—",
              String(c.campaign_count),
              formatNumber(c.total_sent),
              `${c.ctr}%`,
              `${c.ctor}%`,
              formatNumber(c.total_influenced_conversions),
            ])}
          />
        </div>
      )}

      {/* Day-of-week heatmap */}
      {facts.by_day.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Day-of-Week</p>
          <div className="grid grid-cols-7 gap-1.5">
            {facts.by_day.map((d) => {
              const maxCtr = Math.max(...facts.by_day.map((x) => x.ctr));
              const intensity = maxCtr > 0 ? d.ctr / maxCtr : 0;
              return (
                <div
                  key={d.bucket}
                  className="text-center rounded-md border border-border p-2"
                  style={{ backgroundColor: `hsl(222, 47%, ${97 - intensity * 15}%)` }}
                >
                  <p className="text-2xs font-medium text-muted-foreground">{d.bucket?.slice(0, 3)}</p>
                  <p className="text-sm font-semibold mt-0.5">{d.ctr}%</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Creative Intelligence Tab ---------- */

function CreativeTab({ facts, insights }: { facts: Facts | null; insights: Insights | null }) {
  if (!facts) return <EmptyState message="No creative analytics data" />;

  const sections = [
    { title: "Opening Style", data: facts.by_opening_style, narrative: insights?.creative_insights?.opening_style_narrative },
    { title: "Tone", data: facts.by_tone, narrative: insights?.creative_insights?.tone_narrative },
    { title: "CTA Strength", data: facts.by_cta_strength, narrative: insights?.creative_insights?.cta_narrative },
    { title: "Emoji Usage", data: facts.by_emoji_bucket, narrative: insights?.creative_insights?.emoji_narrative },
    { title: "Message Length", data: facts.by_message_length, narrative: insights?.creative_insights?.message_length_narrative },
  ];

  const hasSections = sections.some((s) => s.data && s.data.length > 0);
  const hasKeywords = facts.by_keyword && facts.by_keyword.length > 0;

  if (!hasSections && !hasKeywords) {
    return (
      <div className="text-center py-14">
        <MessageSquare className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <h3 className="text-sm font-medium mb-1">Creative Intelligence not included</h3>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Regenerate with Creative Intelligence sections selected to see opening style, tone, CTA, and emoji analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {sections
        .filter((s) => s.data && s.data.length > 0)
        .map((section) => (
          <div key={section.title} className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{section.title}</p>
            <div className="space-y-1.5">
              {section.data.map((item) => {
                const maxCtr = Math.max(...section.data.map((x) => x.ctr));
                const width = maxCtr > 0 ? (item.ctr / maxCtr) * 100 : 0;
                return (
                  <div key={item.label} className="flex items-center gap-2.5">
                    <span className="text-xs text-muted-foreground w-24 shrink-0 truncate">{item.label}</span>
                    <div className="flex-1 h-6 bg-secondary rounded overflow-hidden relative">
                      <div className="h-full bg-primary/15 rounded transition-all" style={{ width: `${width}%` }} />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-2xs font-medium tabular-nums">
                        {item.ctr}%
                      </span>
                    </div>
                    <span className="text-2xs text-muted-foreground w-12 text-right tabular-nums">{item.campaign_count}</span>
                  </div>
                );
              })}
            </div>
            {section.narrative && <NarrativeBox text={section.narrative} />}
          </div>
        ))}

      {hasKeywords && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Keywords</p>
          <DataTable
            headers={["Keyword", "Campaigns", "CTR", "CTOR", "Conversions"]}
            rows={facts.by_keyword.map((k) => [
              k.keyword,
              String(k.campaign_count),
              `${k.ctr}%`,
              `${k.ctor}%`,
              formatNumber(k.total_influenced_conversions),
            ])}
          />
        </div>
      )}
    </div>
  );
}

/* ---------- Timing Tab ---------- */

function TimingTab({ facts, insights }: { facts: Facts | null; insights: Insights | null }) {
  if (!facts) return <EmptyState message="No timing data available" />;

  if (facts.by_day.length === 0 && facts.by_hour.length === 0) {
    return (
      <div className="text-center py-14">
        <Clock className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <h3 className="text-sm font-medium mb-1">Timing analysis not included</h3>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Regenerate with Timing sections selected to see day-of-week and hour performance.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {facts.by_day.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Day-of-Week</p>
          <DataTable
            headers={["Day", "Campaigns", "Sent", "CTR", "CTOR", "Conversions"]}
            rows={facts.by_day.map((d) => [
              d.bucket || "—",
              String(d.campaign_count),
              formatNumber(d.total_sent),
              `${d.ctr}%`,
              `${d.ctor}%`,
              formatNumber(d.total_influenced_conversions),
            ])}
            highlightBest={2}
            metricCol={3}
          />
          {insights?.timing_insights?.best_days && <NarrativeBox text={insights.timing_insights.best_days} />}
        </div>
      )}

      {facts.by_hour.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Time-of-Day</p>
          <DataTable
            headers={["Time Slot", "Campaigns", "Sent", "CTR", "CTOR", "Conversions"]}
            rows={facts.by_hour.map((h) => [
              h.bucket || "—",
              String(h.campaign_count),
              formatNumber(h.total_sent),
              `${h.ctr}%`,
              `${h.ctor}%`,
              formatNumber(h.total_influenced_conversions),
            ])}
            highlightBest={2}
            metricCol={3}
          />
          {insights?.timing_insights?.best_hours && <NarrativeBox text={insights.timing_insights.best_hours} />}
        </div>
      )}
    </div>
  );
}

/* ---------- Performers Tab ---------- */

function PerformersTab({ facts, insights }: { facts: Facts | null; insights: Insights | null }) {
  if (!facts) return <EmptyState message="No performer data available" />;

  if (facts.top_performers.length === 0 && facts.bottom_performers.length === 0) {
    return (
      <div className="text-center py-14">
        <Award className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <h3 className="text-sm font-medium mb-1">Performer analysis not included</h3>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Regenerate with Performer Analysis selected to see campaign rankings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {facts.top_performers.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <TrendingUp className="h-3 w-3 text-emerald-500" /> Top Performers
          </p>
          <div className="space-y-2">
            {facts.top_performers.map((p, i) => (
              <PerformerCard key={i} performer={p} rank={i + 1} type="top" />
            ))}
          </div>
          {insights?.top_performer_analysis && <NarrativeBox text={insights.top_performer_analysis} />}
        </div>
      )}

      {facts.bottom_performers.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <TrendingDown className="h-3 w-3 text-destructive" /> Bottom Performers
          </p>
          <div className="space-y-2">
            {facts.bottom_performers.map((p, i) => (
              <PerformerCard key={i} performer={p} rank={i + 1} type="bottom" />
            ))}
          </div>
          {insights?.bottom_performer_analysis && <NarrativeBox text={insights.bottom_performer_analysis} />}
        </div>
      )}
    </div>
  );
}

function PerformerCard({ performer, rank, type }: { performer: Performer; rank: number; type: "top" | "bottom" }) {
  const accent = type === "top" ? "border-emerald-100 bg-emerald-50/30" : "border-red-100 bg-red-50/30";
  const badge = type === "top" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700";

  return (
    <div className={`rounded-md border ${accent} px-4 py-3`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`text-2xs font-bold px-1.5 py-0.5 rounded ${badge}`}>#{rank}</span>
          <h4 className="text-sm font-medium truncate">{performer.campaign_name}</h4>
        </div>
        <div className="flex items-center gap-3 text-2xs text-muted-foreground shrink-0 ml-3">
          <span>CTR <strong className="text-foreground">{performer.ctr}%</strong></span>
          <span>CTOR <strong className="text-foreground">{performer.ctor}%</strong></span>
          <span>Conv <strong className="text-foreground">{formatNumber(performer.influenced_conversions)}</strong></span>
        </div>
      </div>
      {performer.message && (
        <p className="text-2xs text-muted-foreground bg-background/60 rounded px-2 py-1.5 mt-2 line-clamp-2">
          {performer.title && <strong>{performer.title}: </strong>}
          {performer.message}
        </p>
      )}
    </div>
  );
}

/* ---------- Recommendations Tab ---------- */

function RecommendationsTab({ insights }: { insights: Insights | null }) {
  if (!insights?.recommendations?.length) {
    return <EmptyState message="No recommendations generated for this report" />;
  }

  return (
    <div className="space-y-3">
      {insights.recommendations.map((rec, i) => (
        <div key={i} className="rounded-md border border-border px-4 py-3.5">
          <div className="flex items-start gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-2xs">
              {rec.priority}
            </div>
            <div className="flex-1 min-w-0 space-y-2">
              <p className="text-sm font-medium leading-relaxed">{rec.action}</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="rounded-md bg-emerald-50 px-3 py-2">
                  <p className="text-2xs uppercase font-medium text-emerald-600 mb-0.5">Impact</p>
                  <p className="text-xs text-emerald-800">{rec.expected_impact}</p>
                </div>
                <div className="rounded-md bg-blue-50 px-3 py-2">
                  <p className="text-2xs uppercase font-medium text-blue-600 mb-0.5">Rationale</p>
                  <p className="text-xs text-blue-800">{rec.rationale}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Shared ---------- */

function DataTable({
  headers, rows, highlightBest, metricCol,
}: {
  headers: string[]; rows: string[][]; highlightBest?: number; metricCol?: number;
}) {
  let topIndices = new Set<number>();
  if (highlightBest && metricCol !== undefined) {
    const values = rows.map((r, i) => ({ i, v: parseFloat(r[metricCol]) || 0 }));
    values.sort((a, b) => b.v - a.v);
    topIndices = new Set(values.slice(0, highlightBest).map((x) => x.i));
  }

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-secondary/50">
            {headers.map((h) => (
              <th key={h} className="text-left text-2xs font-medium text-muted-foreground py-2 px-3">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={`border-b border-border last:border-0 ${topIndices.has(i) ? "bg-emerald-50/40" : ""}`}>
              {row.map((cell, j) => (
                <td key={j} className="py-2 px-3 text-xs">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NarrativeBox({ text }: { text: string }) {
  return (
    <div className="rounded-md bg-primary/5 border border-primary/10 px-3.5 py-2.5">
      <p className="text-2xs font-medium text-primary/70 mb-0.5 flex items-center gap-1">
        <Zap className="h-2.5 w-2.5" /> AI Insight
      </p>
      <p className="text-xs text-muted-foreground leading-relaxed">{text}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-14">
      <BarChart3 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
