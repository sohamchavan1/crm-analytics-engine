"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitCompareArrows, Download, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  listComparisons,
  deleteComparison,
  getComparisonDownloadUrl,
  type ComparisonSummary,
} from "@/lib/api";

export default function ComparisonsPage() {
  const [comparisons, setComparisons] = useState<ComparisonSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listComparisons(100)
      .then((res) => setComparisons(res.comparisons))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this comparison?")) return;
    try {
      await deleteComparison(id);
      setComparisons((prev) => prev.filter((c) => c.comparison_id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-[1000px] mx-auto">
        <div className="h-6 w-40 bg-secondary rounded mb-4 animate-pulse" />
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-secondary rounded-md animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1000px] mx-auto space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Comparisons</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {comparisons.length} past comparison{comparisons.length !== 1 ? "s" : ""}
        </p>
      </div>

      {comparisons.length === 0 ? (
        <div className="text-center py-16">
          <GitCompareArrows className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No comparisons yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            Compare two reports from the Reports page or after generating a report
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {comparisons.map((c) => (
            <div
              key={c.comparison_id}
              className="flex items-center justify-between rounded-md border border-border px-4 py-3 hover:bg-secondary/30 transition-colors"
            >
              <Link
                href={`/compare?a=${c.run_a_id}&b=${c.run_b_id}`}
                className="flex-1 min-w-0"
              >
                <div className="flex items-center gap-2.5">
                  <GitCompareArrows className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">
                      {c.company} · {c.vertical_code}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-2xs text-muted-foreground">{c.run_a_period}</span>
                      <span className="text-2xs text-muted-foreground">vs</span>
                      <span className="text-2xs text-muted-foreground">{c.run_b_period}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{c.summary}</p>
                  </div>
                </div>
              </Link>
              <div className="flex items-center gap-1 shrink-0 ml-3">
                <a href={getComparisonDownloadUrl(c.comparison_id)}>
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <Download className="h-3.5 w-3.5" />
                  </Button>
                </a>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => handleDelete(c.comparison_id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
