"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileText, Download, Trash2, GitCompareArrows } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  listReports,
  getDownloadUrl,
  deleteReport,
  type ReportSummary,
} from "@/lib/api";

export default function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    listReports({ limit: 100 })
      .then((res) => setReports(res.reports))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (runId: string, company: string) => {
    if (!confirm(`Delete report for "${company}"? This cannot be undone.`)) return;
    try {
      await deleteReport(runId);
      setReports((prev) => prev.filter((r) => r.run_id !== runId));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(runId);
        return next;
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const toggleSelect = (runId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        if (next.size >= 2) {
          const first = next.values().next().value;
          if (first) next.delete(first);
        }
        next.add(runId);
      }
      return next;
    });
  };

  const handleCompare = () => {
    const ids = Array.from(selected);
    if (ids.length !== 2) return;
    router.push(`/compare?a=${ids[0]}&b=${ids[1]}`);
  };

  const canCompare = () => {
    if (selected.size !== 2) return false;
    const ids = Array.from(selected);
    const a = reports.find((r) => r.run_id === ids[0]);
    const b = reports.find((r) => r.run_id === ids[1]);
    if (!a || !b) return false;
    return a.company.toLowerCase() === b.company.toLowerCase();
  };

  if (loading) {
    return (
      <div className="p-6 max-w-[1000px] mx-auto">
        <div className="h-6 w-32 bg-secondary rounded mb-4 animate-pulse" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-secondary rounded-md animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1000px] mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Reports</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {reports.length} generated reports
          </p>
        </div>
        {selected.size === 2 && (
          <Button
            size="sm"
            onClick={handleCompare}
            disabled={!canCompare()}
            title={!canCompare() ? "Select two reports from the same brand" : undefined}
          >
            <GitCompareArrows className="h-3.5 w-3.5 mr-1.5" />
            Compare
          </Button>
        )}
      </div>

      {selected.size === 1 && (
        <p className="text-2xs text-muted-foreground">
          Select one more report from the same brand to compare
        </p>
      )}
      {selected.size === 2 && !canCompare() && (
        <p className="text-2xs text-destructive">
          Both reports must be from the same brand
        </p>
      )}

      {reports.length === 0 ? (
        <div className="text-center py-16">
          <FileText className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No reports generated yet</p>
        </div>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-secondary/50">
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5 w-8"></th>
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5">Report</th>
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5">Campaigns</th>
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5">Channels</th>
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5">Period</th>
                <th className="text-left text-2xs font-medium text-muted-foreground px-4 py-2.5">Status</th>
                <th className="text-right text-2xs font-medium text-muted-foreground px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => {
                const isSelected = selected.has(report.run_id);
                return (
                  <tr
                    key={report.run_id}
                    className={`border-b border-border last:border-0 transition-colors ${
                      isSelected ? "bg-primary/5" : "hover:bg-secondary/30"
                    }`}
                  >
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleSelect(report.run_id)}
                        className={`flex h-4 w-4 items-center justify-center rounded border transition-colors ${
                          isSelected
                            ? "border-primary bg-primary"
                            : "border-muted-foreground/30 hover:border-muted-foreground"
                        }`}
                      >
                        {isSelected && (
                          <svg className="h-2.5 w-2.5 text-primary-foreground" viewBox="0 0 12 12" fill="none">
                            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/reports/${report.run_id}`} className="text-sm font-medium hover:underline">
                        {report.company} · {report.vertical_code}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{report.campaign_count}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{report.channels?.join(", ") || "—"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {report.date_range_start ? `${report.date_range_start} — ${report.date_range_end}` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={report.status === "complete" ? "success" : report.status === "failed" ? "destructive" : "warning"}>
                        {report.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {report.status === "complete" && (
                          <a href={getDownloadUrl(report.run_id)}>
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                          </a>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                          onClick={(e) => { e.preventDefault(); handleDelete(report.run_id, report.company); }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
