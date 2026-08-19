"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Upload,
  FileSpreadsheet,
  Check,
  Loader2,
  AlertCircle,
  Download,
  Sparkles,
  GitCompareArrows,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  getProfile,
  uploadFile,
  getDownloadUrl,
  listReports,
  type ProfileFull,
  type UploadResult,
} from "@/lib/api";
import { useGeneration } from "@/hooks/use-generation";

type Step = "upload" | "sections" | "progress" | "results";

export default function GeneratePage() {
  const searchParams = useSearchParams();
  const brandName = searchParams.get("brand") || "";

  const [profile, setProfile] = useState<ProfileFull | null>(null);
  const [step, setStep] = useState<Step>("upload");
  const [verticalCode, setVerticalCode] = useState("");

  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set());

  const { isRunning, steps, result, error, startGeneration } = useGeneration();

  useEffect(() => {
    if (brandName) {
      getProfile(brandName).then(setProfile).catch(console.error);
    }
  }, [brandName]);

  const handleFileUpload = useCallback(async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadFile(file);
      setUploadResult(result);
      setSelectedSections(new Set(result.default_sections));
      setStep("sections");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleGenerate = () => {
    if (!uploadResult || !profile) return;
    if (!verticalCode) {
      alert("Please select a vertical before generating the report.");
      return;
    }
    setStep("progress");
    startGeneration({
      upload_id: uploadResult.upload_id,
      company: profile.company_name,
      vertical_code: verticalCode,
      sections: Array.from(selectedSections),
    });
  };

  useEffect(() => {
    if (result) setStep("results");
  }, [result]);

  return (
    <div className="p-6 max-w-[800px] mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-lg font-semibold">Generate Report</h1>
          {profile && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {profile.company_name} · {profile.industry}
            </p>
          )}
        </div>
      </div>

      {/* Step Indicator */}
      <StepIndicator currentStep={step} />

      {/* Vertical Selection */}
      {profile && (step === "upload" || step === "sections") && (
        <section className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Vertical <span className="text-destructive">*</span>
          </p>
          {profile.verticals.length > 0 ? (
            <>
              <div className="flex flex-wrap gap-2">
                {profile.verticals.map((v) => (
                  <button
                    key={v.code}
                    onClick={() => setVerticalCode(v.code)}
                    className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-colors ${
                      verticalCode === v.code
                        ? "border-primary bg-primary/5 text-foreground"
                        : "border-border text-muted-foreground hover:bg-secondary"
                    }`}
                  >
                    {v.name}
                  </button>
                ))}
              </div>
              {!verticalCode && (
                <p className="text-2xs text-destructive">Select a vertical to proceed</p>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No verticals configured.{" "}
              <Link href={`/brands/${encodeURIComponent(profile.company_name)}`} className="text-primary underline">
                Add one
              </Link>
            </p>
          )}
        </section>
      )}

      {step === "upload" && (
        <UploadStep uploading={uploading} error={uploadError} onFileSelect={handleFileUpload} />
      )}

      {step === "sections" && uploadResult && (
        <SectionStep
          uploadResult={uploadResult}
          selectedSections={selectedSections}
          verticalSelected={!!verticalCode}
          onToggle={(id) => {
            const next = new Set(selectedSections);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            setSelectedSections(next);
          }}
          onGenerate={handleGenerate}
          onBack={() => setStep("upload")}
        />
      )}

      {step === "progress" && (
        <ProgressStep steps={steps} error={error} isRunning={isRunning} />
      )}

      {step === "results" && result && (
        <ResultsStep result={result} company={profile?.company_name} verticalCode={verticalCode} />
      )}
    </div>
  );
}

/* ---------- Sub-components ---------- */

function StepIndicator({ currentStep }: { currentStep: Step }) {
  const allSteps = [
    { key: "upload", label: "Upload" },
    { key: "sections", label: "Sections" },
    { key: "progress", label: "Generating" },
    { key: "results", label: "Done" },
  ];
  const currentIndex = allSteps.findIndex((s) => s.key === currentStep);

  return (
    <div className="flex items-center gap-1.5">
      {allSteps.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1.5">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-2xs font-medium ${
              i <= currentIndex
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            }`}
          >
            {i < currentIndex ? <Check className="h-3 w-3" /> : i + 1}
          </div>
          <span className={`text-xs ${i <= currentIndex ? "text-foreground font-medium" : "text-muted-foreground"}`}>
            {s.label}
          </span>
          {i < allSteps.length - 1 && (
            <div className="w-6 h-px bg-border mx-0.5" />
          )}
        </div>
      ))}
    </div>
  );
}

function UploadStep({
  uploading, error, onFileSelect,
}: {
  uploading: boolean; error: string | null; onFileSelect: (file: File) => void;
}) {
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
      className="flex flex-col items-center justify-center rounded-md border-2 border-dashed border-border hover:border-primary/40 transition-colors py-14 px-6 cursor-pointer"
    >
      {uploading ? (
        <>
          <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
          <p className="text-sm font-medium">Scanning file...</p>
        </>
      ) : (
        <>
          <Upload className="h-8 w-8 text-muted-foreground/60 mb-3" />
          <p className="text-sm font-medium">Drop your CRM export here</p>
          <p className="text-xs text-muted-foreground mt-1">
            Supports CleverTap and MoEngage exports (.csv, .xlsx)
          </p>
        </>
      )}
      <input id="file-input" type="file" accept=".csv,.xlsx,.xls" onChange={handleChange} className="hidden" />
      {error && (
        <div className="mt-4 flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {error}
        </div>
      )}
    </div>
  );
}

function SectionStep({
  uploadResult, selectedSections, verticalSelected, onToggle, onGenerate, onBack,
}: {
  uploadResult: UploadResult; selectedSections: Set<string>; verticalSelected: boolean;
  onToggle: (id: string) => void; onGenerate: () => void; onBack: () => void;
}) {
  return (
    <div className="space-y-4">
      {/* File summary */}
      <div className="flex items-center gap-3 rounded-md border border-border px-4 py-3">
        <FileSpreadsheet className="h-4 w-4 text-primary shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{uploadResult.filename}</p>
          <p className="text-2xs text-muted-foreground">
            {uploadResult.data_profile.campaign_count} campaigns · {uploadResult.platform}
            {uploadResult.data_profile.channels.length > 0 && ` · ${uploadResult.data_profile.channels.join(", ")}`}
          </p>
        </div>
      </div>

      {/* Section picker */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Report Sections
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {uploadResult.available_sections.map((section) => {
            const isSelected = selectedSections.has(section.id);
            return (
              <button
                key={section.id}
                onClick={() => onToggle(section.id)}
                className={`flex items-start gap-2.5 rounded-md border px-3.5 py-3 text-left transition-all ${
                  isSelected
                    ? "border-primary/40 bg-primary/5"
                    : "border-border hover:bg-secondary/50"
                }`}
              >
                <div
                  className={`mt-0.5 flex h-4 w-4 items-center justify-center rounded border shrink-0 ${
                    isSelected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/30"
                  }`}
                >
                  {isSelected && <Check className="h-2.5 w-2.5" />}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{section.name}</p>
                  <p className="text-2xs text-muted-foreground mt-0.5">{section.description}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between pt-2">
        <Button variant="outline" size="sm" onClick={onBack}>Back</Button>
        <Button
          size="sm"
          onClick={onGenerate}
          disabled={selectedSections.size === 0 || !verticalSelected}
        >
          <Sparkles className="h-3.5 w-3.5 mr-1.5" />
          Generate Report
        </Button>
      </div>
    </div>
  );
}

function ProgressStep({
  steps, error, isRunning,
}: {
  steps: { step: number; total: number; message: string; detail?: string | null; status: string }[];
  error: string | null; isRunning: boolean;
}) {
  return (
    <div className="rounded-md border border-border p-6">
      <div className="text-center mb-6">
        {isRunning ? (
          <Loader2 className="h-6 w-6 text-primary animate-spin mx-auto mb-2" />
        ) : error ? (
          <AlertCircle className="h-6 w-6 text-destructive mx-auto mb-2" />
        ) : (
          <Check className="h-6 w-6 text-primary mx-auto mb-2" />
        )}
        <h3 className="text-sm font-semibold">
          {error ? "Generation Failed" : isRunning ? "Generating Report..." : "Complete"}
        </h3>
        {isRunning && (
          <p className="text-2xs text-muted-foreground mt-0.5">~1-2 minutes</p>
        )}
      </div>

      <div className="space-y-2 max-w-sm mx-auto">
        {steps
          .filter((s) => s.step > 0 || (s.step === 0 && steps.length === 1))
          .map((s, i, arr) => {
            const isLatest = i === arr.length - 1 && isRunning;
            const isDone = s.status === "complete" || (!isLatest && isRunning);
            return (
              <div key={s.step} className="flex items-start gap-2.5">
                <div className="mt-0.5 shrink-0">
                  {isLatest && isRunning ? (
                    <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
                  ) : isDone ? (
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <div className="h-3.5 w-3.5 rounded-full border border-muted-foreground/30" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <span className={`text-xs ${isLatest && isRunning ? "font-medium text-foreground" : "text-muted-foreground"}`}>
                    {s.message}
                  </span>
                  {s.detail && (
                    <p className="text-2xs text-muted-foreground/70 truncate">{s.detail}</p>
                  )}
                </div>
                {s.step > 0 && (
                  <span className="text-2xs text-muted-foreground/50 tabular-nums shrink-0">
                    {s.step}/{s.total}
                  </span>
                )}
              </div>
            );
          })}
      </div>

      {isRunning && steps.length > 0 && (
        <div className="mt-5 max-w-sm mx-auto">
          <div className="h-1 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.max(3, (steps[steps.length - 1].step / steps[steps.length - 1].total) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-5 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-2.5 text-sm text-destructive text-center">
          {error}
        </div>
      )}
    </div>
  );
}

function ResultsStep({
  result, company, verticalCode,
}: {
  result: { report_path: string; run_id?: string; message: string };
  company?: string;
  verticalCode?: string;
}) {
  const [pastReports, setPastReports] = useState<{ run_id: string; date_range_start: string | null; date_range_end: string | null; campaign_count: number; vertical_code: string }[]>([]);
  const [selectedCompare, setSelectedCompare] = useState<string | null>(null);

  useEffect(() => {
    if (!company || !result.run_id) return;
    listReports({ company, limit: 50 })
      .then((res) => {
        const others = res.reports.filter(
          (r) => r.run_id !== result.run_id && r.status === "complete" &&
          r.vertical_code === verticalCode
        );
        setPastReports(others);
      })
      .catch(() => {});
  }, [company, verticalCode, result.run_id]);

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border p-8 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 mb-4">
          <Sparkles className="h-6 w-6 text-primary" />
        </div>
        <h3 className="text-base font-semibold mb-1">Report Ready</h3>
        <p className="text-xs text-muted-foreground mb-5">
          Your CRM Intelligence Report has been generated
        </p>

        <div className="flex justify-center gap-2 flex-wrap">
          {result.run_id && (
            <Link href={`/reports/${result.run_id}`}>
              <Button size="sm">
                <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                View Report
              </Button>
            </Link>
          )}
          {result.run_id && (
            <a href={getDownloadUrl(result.run_id)}>
              <Button variant="outline" size="sm">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Download DOCX
              </Button>
            </a>
          )}
          <Link href="/">
            <Button variant="ghost" size="sm">Dashboard</Button>
          </Link>
        </div>
      </div>

      {/* Compare with past reports — full list, user picks */}
      {pastReports.length > 0 && result.run_id && (
        <div className="rounded-md border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <GitCompareArrows className="h-3.5 w-3.5 text-muted-foreground" />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Compare with a past report
            </p>
          </div>
          <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
            {pastReports.map((r) => (
              <button
                key={r.run_id}
                onClick={() => setSelectedCompare(r.run_id === selectedCompare ? null : r.run_id)}
                className={`w-full flex items-center justify-between rounded-md border px-3 py-2.5 text-left transition-colors ${
                  selectedCompare === r.run_id
                    ? "border-primary/40 bg-primary/5"
                    : "border-border hover:bg-secondary/50"
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {r.date_range_start && r.date_range_end
                      ? `${r.date_range_start} — ${r.date_range_end}`
                      : "Date range unavailable"}
                  </p>
                  <p className="text-2xs text-muted-foreground mt-0.5">
                    {r.campaign_count} campaigns · {r.vertical_code}
                  </p>
                </div>
                <div className={`flex h-4 w-4 items-center justify-center rounded-full border shrink-0 ${
                  selectedCompare === r.run_id ? "border-primary bg-primary" : "border-muted-foreground/30"
                }`}>
                  {selectedCompare === r.run_id && (
                    <div className="h-2 w-2 rounded-full bg-primary-foreground" />
                  )}
                </div>
              </button>
            ))}
          </div>
          {selectedCompare && (
            <Link href={`/compare?a=${selectedCompare}&b=${result.run_id}`}>
              <Button size="sm" className="w-full">
                <GitCompareArrows className="h-3.5 w-3.5 mr-1.5" />
                Compare Reports
              </Button>
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
