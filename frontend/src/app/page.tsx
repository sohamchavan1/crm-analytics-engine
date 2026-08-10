"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Play, Pencil, FileText, Building2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { listProfiles, listReports, type ProfileSummary, type ReportSummary } from "@/lib/api";

export default function HomePage() {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [profilesRes, reportsRes] = await Promise.all([
          listProfiles(),
          listReports({ limit: 5 }),
        ]);
        setProfiles(profilesRes.profiles);
        setReports(reportsRes.reports);
      } catch (err) {
        console.error("Failed to load data:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (!loading && profiles.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="p-6 max-w-[1100px] mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Dashboard</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate and manage CRM intelligence reports
          </p>
        </div>
        <Link href="/brands/new">
          <Button size="sm">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            New Brand
          </Button>
        </Link>
      </div>

      <section>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
          Brands
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {profiles.map((profile) => (
            <BrandCard key={profile.company_name} profile={profile} />
          ))}
        </div>
      </section>

      {reports.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recent Reports
            </p>
            <Link href="/reports" className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-1.5">
            {reports.map((report) => (
              <ReportRow key={report.run_id} report={report} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function BrandCard({ profile }: { profile: ProfileSummary }) {
  return (
    <Card className="group hover:border-foreground/20 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start gap-3 mb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-secondary shrink-0">
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate">{profile.company_name}</p>
            <p className="text-2xs text-muted-foreground">{profile.industry}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 mb-3">
          {profile.verticals.map((v) => (
            <Badge key={v.code} variant="secondary">{v.name}</Badge>
          ))}
          {profile.verticals.length === 0 && (
            <span className="text-2xs text-muted-foreground">No verticals</span>
          )}
        </div>
        <div className="flex gap-2">
          <Link href={`/generate?brand=${encodeURIComponent(profile.company_name)}`} className="flex-1">
            <Button className="w-full" size="sm">
              <Play className="h-3 w-3 mr-1.5" />
              Generate
            </Button>
          </Link>
          <Link href={`/brands/${encodeURIComponent(profile.company_name)}`}>
            <Button variant="outline" size="sm">
              <Pencil className="h-3 w-3" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportRow({ report }: { report: ReportSummary }) {
  const statusVariant =
    report.status === "complete" ? "success" : report.status === "failed" ? "destructive" : "warning";

  return (
    <Link
      href={`/reports/${report.run_id}`}
      className="flex items-center justify-between rounded-md border border-border px-4 py-3 hover:bg-secondary/50 transition-colors group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-medium truncate group-hover:text-foreground">
            {report.company} · {report.vertical_code}
          </p>
          <p className="text-2xs text-muted-foreground">
            {report.campaign_count} campaigns · {report.date_range_start && report.date_range_end
              ? `${report.date_range_start} — ${report.date_range_end}`
              : "Processing..."}
          </p>
        </div>
      </div>
      <Badge variant={statusVariant as any}>{report.status}</Badge>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="text-center max-w-sm">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-secondary mb-4">
          <Building2 className="h-6 w-6 text-muted-foreground" />
        </div>
        <h2 className="text-base font-semibold mb-1">Welcome to CRM Intelligence</h2>
        <p className="text-sm text-muted-foreground mb-5">
          Turn CRM campaign exports into executive intelligence reports. Start by creating a brand profile.
        </p>
        <Link href="/brands/new">
          <Button>
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Create Brand
          </Button>
        </Link>
      </div>
    </div>
  );
}
