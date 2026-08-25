"use client";

import { useEffect, useState } from "react";
import {
  Cpu,
  FileBarChart,
  HardDrive,
  Info,
  Loader2,
  Check,
  Trash2,
  RefreshCw,
  Save,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface EngineSettings {
  l1_temperature: number;
  l2_temperature: number;
  ranking_metric: string;
  performers_count: number;
  label_separator: string;
  auto_cleanup_uploads: boolean;
  system: {
    aws_region: string;
    model_id: string;
    engine_version: string;
  };
}

interface StorageStats {
  uploads: { file_count: number; size_bytes: number };
  runs: { file_count: number; size_bytes: number };
  facts: { file_count: number; size_bytes: number };
  insights: { file_count: number; size_bytes: number };
  reports: { file_count: number; size_bytes: number };
  total_size_bytes: number;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<EngineSettings | null>(null);
  const [storage, setStorage] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [settingsRes, storageRes, healthRes] = await Promise.allSettled([
          fetch("/api/settings").then((r) => r.json()),
          fetch("/api/settings/storage").then((r) => r.json()),
          fetch("/api/health").then((r) => r.ok),
        ]);
        if (settingsRes.status === "fulfilled") setSettings(settingsRes.value);
        if (storageRes.status === "fulfilled") setStorage(storageRes.value);
        if (healthRes.status === "fulfilled") setHealthOk(healthRes.value);
      } catch (err) {
        console.error("Failed to load settings:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          l1_temperature: settings.l1_temperature,
          l2_temperature: settings.l2_temperature,
          ranking_metric: settings.ranking_metric,
          performers_count: settings.performers_count,
          label_separator: settings.label_separator,
          auto_cleanup_uploads: settings.auto_cleanup_uploads,
        }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (err) {
      console.error("Save failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleClearUploads = async () => {
    if (!confirm("Delete all uploaded temp files?")) return;
    try {
      await fetch("/api/settings/uploads", { method: "DELETE" });
      const res = await fetch("/api/settings/storage");
      if (res.ok) setStorage(await res.json());
    } catch (err) {
      console.error("Clear uploads failed:", err);
    }
  };

  const refreshStorage = async () => {
    const res = await fetch("/api/settings/storage");
    if (res.ok) setStorage(await res.json());
  };

  if (loading) {
    return (
      <div className="p-6 max-w-[760px] mx-auto">
        <div className="h-6 w-32 bg-secondary rounded mb-4 animate-pulse" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-secondary rounded-md animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[760px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Settings</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Engine configuration and preferences
          </p>
        </div>
        <Button size="sm" onClick={handleSave} disabled={saving || !settings}>
          {saved ? (
            <><Check className="h-3.5 w-3.5 mr-1.5" />Saved</>
          ) : saving ? (
            <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Saving</>
          ) : (
            <><Save className="h-3.5 w-3.5 mr-1.5" />Save</>
          )}
        </Button>
      </div>

      {/* AI Configuration */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">AI Configuration</p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-md bg-secondary/50 border border-border px-3 py-2.5">
            <p className="text-2xs uppercase font-medium text-muted-foreground mb-0.5">Model</p>
            <p className="text-sm font-medium">Claude Opus 4.6</p>
          </div>
          <div className="rounded-md bg-secondary/50 border border-border px-3 py-2.5">
            <p className="text-2xs uppercase font-medium text-muted-foreground mb-0.5">Region</p>
            <p className="text-sm font-medium">{settings?.system.aws_region || "us-east-1"}</p>
          </div>
          <div className="rounded-md bg-secondary/50 border border-border px-3 py-2.5">
            <p className="text-2xs uppercase font-medium text-muted-foreground mb-0.5">Provider</p>
            <p className="text-sm font-medium">Amazon Bedrock</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          <div>
            <label className="text-xs font-medium text-foreground block mb-1">
              L1 Temperature (Classification)
            </label>
            <p className="text-2xs text-muted-foreground mb-2">
              Lower = more deterministic. Recommended: 0.
            </p>
            <input
              type="range"
              min="0" max="1" step="0.1"
              value={settings?.l1_temperature ?? 0}
              onChange={(e) => setSettings((s) => s ? { ...s, l1_temperature: parseFloat(e.target.value) } : s)}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-2xs text-muted-foreground mt-1">
              <span>0</span>
              <span className="font-medium text-foreground">{settings?.l1_temperature ?? 0}</span>
              <span>1</span>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1">
              L2 Temperature (Narration)
            </label>
            <p className="text-2xs text-muted-foreground mb-2">
              Slightly higher for natural narratives. Recommended: 0.3.
            </p>
            <input
              type="range"
              min="0" max="1" step="0.1"
              value={settings?.l2_temperature ?? 0.3}
              onChange={(e) => setSettings((s) => s ? { ...s, l2_temperature: parseFloat(e.target.value) } : s)}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-2xs text-muted-foreground mt-1">
              <span>0</span>
              <span className="font-medium text-foreground">{settings?.l2_temperature ?? 0.3}</span>
              <span>1</span>
            </div>
          </div>
        </div>
      </section>

      {/* Report Defaults */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <FileBarChart className="h-3.5 w-3.5 text-muted-foreground" />
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Report Defaults</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">Ranking Metric</label>
            <select
              value={settings?.ranking_metric ?? "ctr"}
              onChange={(e) => setSettings((s) => s ? { ...s, ranking_metric: e.target.value } : s)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ctr">CTR</option>
              <option value="ctor">CTOR</option>
              <option value="conversions">Conversions</option>
            </select>
            <p className="text-2xs text-muted-foreground">How performers are ranked</p>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">Performers Count</label>
            <input
              type="number"
              min={1} max={20}
              value={settings?.performers_count ?? 5}
              onChange={(e) => setSettings((s) => s ? { ...s, performers_count: parseInt(e.target.value) || 5 } : s)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <p className="text-2xs text-muted-foreground">Top/bottom to highlight</p>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">Label Separator</label>
            <input
              type="text"
              value={settings?.label_separator ?? "|"}
              onChange={(e) => setSettings((s) => s ? { ...s, label_separator: e.target.value } : s)}
              maxLength={3}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <p className="text-2xs text-muted-foreground">Multi-value separator in exports</p>
          </div>
        </div>
      </section>

      {/* Storage */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="h-3.5 w-3.5 text-muted-foreground" />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Storage</p>
          </div>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={refreshStorage}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Auto-cleanup toggle */}
        <div className="flex items-center justify-between rounded-md border border-border px-4 py-3">
          <div>
            <p className="text-sm font-medium">Auto-cleanup uploads</p>
            <p className="text-2xs text-muted-foreground mt-0.5">
              Delete temp files after report generation
            </p>
          </div>
          <button
            onClick={() => setSettings((s) => s ? { ...s, auto_cleanup_uploads: !s.auto_cleanup_uploads } : s)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              settings?.auto_cleanup_uploads ? "bg-primary" : "bg-muted-foreground/30"
            }`}
          >
            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
              settings?.auto_cleanup_uploads ? "translate-x-[18px]" : "translate-x-[3px]"
            }`} />
          </button>
        </div>

        {storage && (
          <div className="grid grid-cols-5 gap-2">
            {(["uploads", "reports", "runs", "facts", "insights"] as const).map((key) => (
              <div key={key} className="rounded-md border border-border px-2.5 py-2 text-center">
                <p className="text-sm font-semibold tabular-nums">{storage[key].file_count}</p>
                <p className="text-2xs text-muted-foreground capitalize">{key}</p>
                <p className="text-2xs text-muted-foreground">{formatBytes(storage[key].size_bytes)}</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Total: <span className="font-medium text-foreground">{storage ? formatBytes(storage.total_size_bytes) : "—"}</span>
          </p>
          <Button variant="outline" size="sm" onClick={handleClearUploads} className="text-destructive hover:text-destructive">
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Clear Uploads
          </Button>
        </div>
      </section>

      {/* About */}
      <section className="flex items-center justify-between rounded-md border border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">CRM Intelligence Engine</p>
            <p className="text-2xs text-muted-foreground">
              v{settings?.system.engine_version || "0.1.0"} · Attributics
            </p>
          </div>
        </div>
        <Badge variant={healthOk ? "success" : "destructive"}>
          {healthOk ? "Connected" : "Offline"}
        </Badge>
      </section>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
