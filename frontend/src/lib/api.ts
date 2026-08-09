/**
 * API client for CRM Intelligence Engine backend.
 *
 * All calls go through Next.js rewrites → FastAPI at :8000.
 */

const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

export interface ProfileSummary {
  company_name: string;
  industry: string;
  description: string | null;
  verticals_count: number;
  verticals: { name: string; code: string }[];
  selected_sections: string[];
  created_at: string;
}

export interface ProfileFull {
  company_name: string;
  industry: string;
  description: string | null;
  business_model: string | null;
  brand_positioning: string | null;
  products_services: string | null;
  target_audience: string | null;
  website: string | null;
  crm_platforms: string[];
  marketing_strategy: string | null;
  communication_goals: string | null;
  retention_strategy: string | null;
  brand_voice: string | null;
  business_constraints: string | null;
  kpis: string | null;
  selected_sections: string[];
  ranking_metric: string;
  performers_count: number;
  offer_extraction_pattern: string | null;
  label_separator: string;
  verticals: VerticalProfile[];
  observations: Observation[];
  created_at: string;
  updated_at: string;
}

export interface VerticalProfile {
  name: string;
  code: string;
  business_objective: string | null;
  primary_kpi: string | null;
  typical_cta: string | null;
  target_audience: string | null;
  success_metrics: string | null;
  notes: string | null;
}

export interface Observation {
  content: string;
  category: string;
  source: string | null;
  created_at: string;
}

export async function listProfiles() {
  return request<{ profiles: ProfileSummary[] }>("/profiles");
}

export async function getProfile(companyName: string) {
  return request<ProfileFull>(`/profiles/${encodeURIComponent(companyName)}`);
}

export async function createProfile(data: Record<string, unknown>) {
  return request<{ status: string; company_name: string }>("/profiles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProfile(
  companyName: string,
  data: Record<string, unknown>
) {
  return request<{ status: string }>(
    `/profiles/${encodeURIComponent(companyName)}`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export async function deleteProfile(companyName: string) {
  return request<{ status: string }>(
    `/profiles/${encodeURIComponent(companyName)}`,
    { method: "DELETE" }
  );
}

export async function addVertical(
  companyName: string,
  data: Record<string, unknown>
) {
  return request<{ status: string }>(
    `/profiles/${encodeURIComponent(companyName)}/verticals`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function updateVertical(
  companyName: string,
  verticalCode: string,
  data: Record<string, unknown>
) {
  return request<{ status: string }>(
    `/profiles/${encodeURIComponent(companyName)}/verticals/${encodeURIComponent(verticalCode)}`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export async function deleteVertical(companyName: string, verticalCode: string) {
  return request<{ status: string }>(
    `/profiles/${encodeURIComponent(companyName)}/verticals/${encodeURIComponent(verticalCode)}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

export interface SectionDef {
  id: string;
  name: string;
  description: string;
  requires_l1: boolean;
  l1_dimensions: string[];
  requires_data: string[];
  default_verticals: string[];
}

export async function listSections() {
  return request<{ sections: SectionDef[] }>("/sections");
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export interface ReportSummary {
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

export async function listReports(params?: {
  company?: string;
  vertical?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.company) query.set("company", params.company);
  if (params?.vertical) query.set("vertical", params.vertical);
  if (params?.limit) query.set("limit", String(params.limit));

  const qs = query.toString();
  return request<{ reports: ReportSummary[]; total: number }>(
    `/reports${qs ? `?${qs}` : ""}`
  );
}

export async function getReport(runId: string) {
  return request<{
    run: Record<string, unknown>;
    facts_summary: Record<string, unknown> | null;
    insights_summary: Record<string, unknown> | null;
  }>(`/reports/${runId}`);
}

export async function deleteReport(runId: string) {
  return request<{ status: string; run_id: string }>(`/reports/${runId}`, {
    method: "DELETE",
  });
}

export function getDownloadUrl(runId: string) {
  return `${BASE}/reports/${runId}/download`;
}

// ---------------------------------------------------------------------------
// Generate (upload + run)
// ---------------------------------------------------------------------------

export interface UploadResult {
  upload_id: string;
  filename: string;
  platform: string;
  data_profile: {
    campaign_count: number;
    channels: string[];
    has_messages: boolean;
    has_labels: boolean;
    unique_labels: string[];
    has_offer_pattern: boolean;
    capabilities: string[];
  };
  available_sections: { id: string; name: string; description: string }[];
  default_sections: string[];
}

export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/generate/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Comparison
// ---------------------------------------------------------------------------

export interface ComparisonResult {
  comparison_id: string;
  run_a: {
    run_id: string;
    company: string;
    vertical_code: string;
    date_range_start: string | null;
    date_range_end: string | null;
    campaign_count: number;
    channels: string[];
    overall: Record<string, number>;
  };
  run_b: {
    run_id: string;
    company: string;
    vertical_code: string;
    date_range_start: string | null;
    date_range_end: string | null;
    campaign_count: number;
    channels: string[];
    overall: Record<string, number>;
  };
  comparison: {
    summary: string;
    metrics_delta: {
      ctr_change: number;
      ctor_change: number;
      conversion_change: number;
      sent_change: number;
      delivery_rate_change: number;
    };
    improvements: string[];
    declines: string[];
    strategy_shifts: string[];
    recommendation: string;
    context_note: string | null;
  };
}

export async function compareReports(runIdA: string, runIdB: string) {
  return request<ComparisonResult>("/compare", {
    method: "POST",
    body: JSON.stringify({ run_id_a: runIdA, run_id_b: runIdB }),
  });
}

export interface ComparisonSummary {
  comparison_id: string;
  company: string;
  vertical_code: string;
  run_a_period: string;
  run_b_period: string;
  run_a_id: string;
  run_b_id: string;
  summary: string;
  created_at: string;
}

export async function listComparisons(limit?: number) {
  const qs = limit ? `?limit=${limit}` : "";
  return request<{ comparisons: ComparisonSummary[]; total: number }>(`/compare${qs}`);
}

export async function deleteComparison(comparisonId: string) {
  return request<{ status: string }>(`/compare/${comparisonId}`, { method: "DELETE" });
}

export function getComparisonDownloadUrl(comparisonId: string) {
  return `${BASE}/compare/${comparisonId}/download`;
}

// ---------------------------------------------------------------------------
// Generate (upload + run)
// ---------------------------------------------------------------------------

export function startGeneration(params: {
  upload_id: string;
  company: string;
  vertical_code: string;
  sections: string[];
}): EventSource {
  // Use form-encoded POST via fetch, but we need SSE...
  // SSE requires GET or EventSource, so we'll use a custom approach
  // Actually we'll post the params and get back SSE stream
  const formData = new URLSearchParams();
  formData.set("upload_id", params.upload_id);
  formData.set("company", params.company);
  formData.set("vertical_code", params.vertical_code);
  formData.set("sections", params.sections.join(","));

  // For SSE with POST, we use fetch + ReadableStream
  // This is handled by the useGeneration hook instead
  throw new Error("Use useGeneration hook for SSE streaming");
}
