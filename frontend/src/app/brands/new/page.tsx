"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { createProfile } from "@/lib/api";

interface VerticalForm {
  name: string;
  code: string;
  business_objective: string;
  primary_kpi: string;
  typical_cta: string;
  target_audience: string;
  success_metrics: string;
  notes: string;
}

const EMPTY_VERTICAL: VerticalForm = {
  name: "",
  code: "",
  business_objective: "",
  primary_kpi: "",
  typical_cta: "",
  target_audience: "",
  success_metrics: "",
  notes: "",
};

const INDUSTRIES = [
  "Travel & Hospitality",
  "Apparel & Fashion Retail",
  "E-commerce & Marketplace",
  "Banking & Financial Services",
  "Insurance",
  "EdTech",
  "HealthTech",
  "Food & Beverage",
  "Media & Entertainment",
  "Real Estate",
  "Automotive",
  "Telecom",
  "FMCG / CPG",
  "SaaS / Technology",
  "Other",
];

export default function NewBrandPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEnrich, setShowEnrich] = useState(false);

  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");
  const [crmPlatform, setCrmPlatform] = useState("");

  const [businessModel, setBusinessModel] = useState("");
  const [brandPositioning, setBrandPositioning] = useState("");
  const [productsServices, setProductsServices] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [website, setWebsite] = useState("");
  const [marketingStrategy, setMarketingStrategy] = useState("");
  const [communicationGoals, setCommunicationGoals] = useState("");
  const [retentionStrategy, setRetentionStrategy] = useState("");
  const [brandVoice, setBrandVoice] = useState("");
  const [businessConstraints, setBusinessConstraints] = useState("");
  const [kpis, setKpis] = useState("");

  const [verticals, setVerticals] = useState<VerticalForm[]>([]);

  const addVertical = () => setVerticals([...verticals, { ...EMPTY_VERTICAL }]);
  const removeVertical = (i: number) => setVerticals(verticals.filter((_, idx) => idx !== i));
  const updateVertical = (i: number, field: keyof VerticalForm, value: string) => {
    const updated = [...verticals];
    updated[i] = { ...updated[i], [field]: value };
    setVerticals(updated);
  };

  const handleSave = async () => {
    if (!companyName.trim() || !industry.trim()) {
      setError("Company name and industry are required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createProfile({
        company_name: companyName.trim(),
        industry,
        description: description || undefined,
        crm_platform: crmPlatform || undefined,
        business_model: businessModel || undefined,
        brand_positioning: brandPositioning || undefined,
        products_services: productsServices || undefined,
        target_audience: targetAudience || undefined,
        website: website || undefined,
        marketing_strategy: marketingStrategy || undefined,
        communication_goals: communicationGoals || undefined,
        retention_strategy: retentionStrategy || undefined,
        brand_voice: brandVoice || undefined,
        business_constraints: businessConstraints || undefined,
        kpis: kpis || undefined,
        verticals: verticals
          .filter((v) => v.name && v.code)
          .map((v) => ({
            name: v.name,
            code: v.code,
            business_objective: v.business_objective || undefined,
            primary_kpi: v.primary_kpi || undefined,
            typical_cta: v.typical_cta || undefined,
            target_audience: v.target_audience || undefined,
            success_metrics: v.success_metrics || undefined,
            notes: v.notes || undefined,
          })),
      });
      router.push("/brands");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-[760px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/brands">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-lg font-semibold">Create Brand Profile</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Set up context for intelligent report generation
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-2.5 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Essentials */}
      <section className="space-y-4">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Essentials
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput
            label="Company Name"
            hint="Brand or business name"
            value={companyName}
            onChange={setCompanyName}
            required
          />
          <FieldSelect
            label="Industry"
            hint="Primary industry vertical"
            value={industry}
            options={INDUSTRIES}
            onChange={setIndustry}
            required
          />
        </div>
        <FieldTextarea
          label="What does this company do?"
          hint="2-3 sentences about the business, its customers, and what it sells"
          value={description}
          onChange={setDescription}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldSelect
            label="CRM Platform"
            hint="Primary marketing automation platform"
            value={crmPlatform}
            options={["CleverTap", "MoEngage", "Braze", "Other"]}
            onChange={setCrmPlatform}
          />
          <FieldInput
            label="Website"
            hint="Company website URL"
            value={website}
            onChange={setWebsite}
            placeholder="https://"
          />
        </div>
      </section>

      {/* Enrichment */}
      <section className="rounded-md border border-border">
        <button
          type="button"
          onClick={() => setShowEnrich(!showEnrich)}
          className="flex items-center justify-between w-full px-4 py-3 text-left"
        >
          <div>
            <p className="text-sm font-medium">Enrich Profile</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Optional — improves report quality
            </p>
          </div>
          {showEnrich ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {showEnrich && (
          <div className="border-t border-border px-4 py-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldTextarea label="Business Model" hint="How the business makes money" value={businessModel} onChange={setBusinessModel} />
              <FieldTextarea label="Brand Positioning" hint="Brand themes and positioning statement" value={brandPositioning} onChange={setBrandPositioning} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldTextarea label="Products & Services" hint="Key products or services offered" value={productsServices} onChange={setProductsServices} />
              <FieldTextarea label="Target Audience" hint="Who the company's customers are" value={targetAudience} onChange={setTargetAudience} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldTextarea label="Communication Goals" hint="What CRM campaigns aim to achieve" value={communicationGoals} onChange={setCommunicationGoals} />
              <FieldTextarea label="Brand Voice" hint="Tone and style, e.g., warm, premium, conversational" value={brandVoice} onChange={setBrandVoice} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldTextarea label="Marketing Strategy" hint="High-level marketing approach" value={marketingStrategy} onChange={setMarketingStrategy} />
              <FieldTextarea label="Retention Strategy" hint="How the business retains customers" value={retentionStrategy} onChange={setRetentionStrategy} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldTextarea label="KPIs" hint="Key business metrics CRM campaigns drive" value={kpis} onChange={setKpis} />
              <FieldTextarea label="Business Constraints" hint="Known limitations or special considerations" value={businessConstraints} onChange={setBusinessConstraints} />
            </div>
          </div>
        )}
      </section>

      {/* Verticals */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Verticals
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Campaign categories (e.g., HFRP, Occupancy, E-commerce)
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={addVertical}>
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Add
          </Button>
        </div>

        {verticals.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8 border border-dashed border-border rounded-md">
            No verticals added yet
          </p>
        ) : (
          <div className="space-y-3">
            {verticals.map((vertical, index) => (
              <VerticalCard
                key={index}
                vertical={vertical}
                index={index}
                onChange={updateVertical}
                onRemove={removeVertical}
              />
            ))}
          </div>
        )}
      </section>

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2 pb-8 border-t border-border">
        <Link href="/brands">
          <Button variant="outline" size="sm">Cancel</Button>
        </Link>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Brand"}
        </Button>
      </div>
    </div>
  );
}

/* ---------- Field components ---------- */

function FieldInput({
  label, hint, value, onChange, required, placeholder,
}: {
  label: string; hint: string; value: string; onChange: (v: string) => void;
  required?: boolean; placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-foreground">
        {label}{required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      <p className="text-2xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function FieldTextarea({
  label, hint, value, onChange,
}: {
  label: string; hint: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-foreground">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-none"
      />
      <p className="text-2xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function FieldSelect({
  label, hint, value, options, onChange, required,
}: {
  label: string; hint: string; value: string; options: string[];
  onChange: (v: string) => void; required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-foreground">
        {label}{required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs ring-offset-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <option value="">Select...</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
      <p className="text-2xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function VerticalCard({
  vertical, index, onChange, onRemove,
}: {
  vertical: VerticalForm; index: number;
  onChange: (i: number, field: keyof VerticalForm, value: string) => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div className="rounded-md border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Badge variant="secondary">Vertical {index + 1}</Badge>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
          onClick={() => onRemove(index)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-2xs font-medium">Name</label>
          <Input value={vertical.name} onChange={(e) => onChange(index, "name", e.target.value)} placeholder="e.g., HFRP" />
        </div>
        <div className="space-y-1">
          <label className="text-2xs font-medium">Code</label>
          <Input value={vertical.code} onChange={(e) => onChange(index, "code", e.target.value)} placeholder="e.g., HFRP" />
        </div>
        <div className="space-y-1">
          <label className="text-2xs font-medium">Business Objective</label>
          <Input value={vertical.business_objective} onChange={(e) => onChange(index, "business_objective", e.target.value)} placeholder="What this vertical aims to achieve" />
        </div>
        <div className="space-y-1">
          <label className="text-2xs font-medium">Primary KPI</label>
          <Input value={vertical.primary_kpi} onChange={(e) => onChange(index, "primary_kpi", e.target.value)} placeholder="e.g., Conversion Rate" />
        </div>
        <div className="space-y-1">
          <label className="text-2xs font-medium">Typical CTA</label>
          <Input value={vertical.typical_cta} onChange={(e) => onChange(index, "typical_cta", e.target.value)} placeholder="e.g., Shop Now" />
        </div>
        <div className="space-y-1">
          <label className="text-2xs font-medium">Target Audience</label>
          <Input value={vertical.target_audience} onChange={(e) => onChange(index, "target_audience", e.target.value)} placeholder="Who this vertical targets" />
        </div>
      </div>
    </div>
  );
}
