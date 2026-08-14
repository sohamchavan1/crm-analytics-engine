"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, Trash2, Save, Check } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  getProfile,
  updateProfile,
  addVertical,
  deleteVertical,
  type ProfileFull,
} from "@/lib/api";

export default function EditBrandPage() {
  const params = useParams();
  const router = useRouter();
  const brandName = decodeURIComponent(params.name as string);

  const [profile, setProfile] = useState<ProfileFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");
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

  const [showNewVertical, setShowNewVertical] = useState(false);
  const [newVerticalName, setNewVerticalName] = useState("");
  const [newVerticalCode, setNewVerticalCode] = useState("");
  const [newVerticalObjective, setNewVerticalObjective] = useState("");
  const [newVerticalKpi, setNewVerticalKpi] = useState("");

  useEffect(() => {
    getProfile(brandName)
      .then((p) => {
        setProfile(p);
        setIndustry(p.industry || "");
        setDescription(p.description || "");
        setBusinessModel(p.business_model || "");
        setBrandPositioning(p.brand_positioning || "");
        setProductsServices(p.products_services || "");
        setTargetAudience(p.target_audience || "");
        setWebsite(p.website || "");
        setMarketingStrategy(p.marketing_strategy || "");
        setCommunicationGoals(p.communication_goals || "");
        setRetentionStrategy(p.retention_strategy || "");
        setBrandVoice(p.brand_voice || "");
        setBusinessConstraints(p.business_constraints || "");
        setKpis(p.kpis || "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [brandName]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await updateProfile(brandName, {
        industry: industry || undefined,
        description: description || undefined,
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
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleAddVertical = async () => {
    if (!newVerticalName || !newVerticalCode) return;
    try {
      await addVertical(brandName, {
        name: newVerticalName,
        code: newVerticalCode,
        business_objective: newVerticalObjective || undefined,
        primary_kpi: newVerticalKpi || undefined,
      });
      const updated = await getProfile(brandName);
      setProfile(updated);
      setShowNewVertical(false);
      setNewVerticalName("");
      setNewVerticalCode("");
      setNewVerticalObjective("");
      setNewVerticalKpi("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add vertical");
    }
  };

  const handleDeleteVertical = async (code: string) => {
    if (!confirm(`Remove vertical "${code}"?`)) return;
    try {
      await deleteVertical(brandName, code);
      const updated = await getProfile(brandName);
      setProfile(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete vertical");
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-[760px] mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-secondary rounded w-48" />
          <div className="h-48 bg-secondary rounded-md" />
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-6 max-w-[760px] mx-auto">
        <p className="text-sm text-destructive">Profile not found: {brandName}</p>
        <Link href="/brands">
          <Button variant="outline" size="sm" className="mt-3">Back</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[760px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/brands">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-semibold">{profile.company_name}</h1>
            <p className="text-xs text-muted-foreground">{profile.industry}</p>
          </div>
        </div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {success ? (
            <><Check className="h-3.5 w-3.5 mr-1.5" />Saved</>
          ) : (
            <><Save className="h-3.5 w-3.5 mr-1.5" />{saving ? "Saving..." : "Save"}</>
          )}
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-2.5 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Brand Identity */}
      <section className="space-y-4">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Brand Identity
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="Industry" value={industry} onChange={setIndustry} />
          <FieldTile label="Website" value={website} onChange={setWebsite} />
        </div>
        <FieldTile label="Description" value={description} onChange={setDescription} multiline />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="Business Model" value={businessModel} onChange={setBusinessModel} multiline />
          <FieldTile label="Brand Positioning" value={brandPositioning} onChange={setBrandPositioning} multiline />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="Products & Services" value={productsServices} onChange={setProductsServices} multiline />
          <FieldTile label="Target Audience" value={targetAudience} onChange={setTargetAudience} multiline />
        </div>
      </section>

      {/* Marketing Context */}
      <section className="space-y-4">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Marketing Context
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="Communication Goals" value={communicationGoals} onChange={setCommunicationGoals} multiline />
          <FieldTile label="Brand Voice" value={brandVoice} onChange={setBrandVoice} multiline />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="Marketing Strategy" value={marketingStrategy} onChange={setMarketingStrategy} multiline />
          <FieldTile label="Retention Strategy" value={retentionStrategy} onChange={setRetentionStrategy} multiline />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldTile label="KPIs" value={kpis} onChange={setKpis} multiline />
          <FieldTile label="Business Constraints" value={businessConstraints} onChange={setBusinessConstraints} multiline />
        </div>
      </section>

      {/* Verticals */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Verticals
          </p>
          <Button variant="outline" size="sm" onClick={() => setShowNewVertical(true)}>
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Add
          </Button>
        </div>

        {profile.verticals.length === 0 && !showNewVertical && (
          <p className="text-sm text-muted-foreground text-center py-8 border border-dashed border-border rounded-md">
            No verticals yet
          </p>
        )}

        {profile.verticals.map((v) => (
          <div
            key={v.code}
            className="flex items-center justify-between rounded-md border border-border px-4 py-3"
          >
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{v.name}</p>
                <Badge variant="secondary">{v.code}</Badge>
              </div>
              {v.business_objective && (
                <p className="text-2xs text-muted-foreground mt-0.5">{v.business_objective}</p>
              )}
              {v.primary_kpi && (
                <p className="text-2xs text-muted-foreground">KPI: {v.primary_kpi}</p>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
              onClick={() => handleDeleteVertical(v.code)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}

        {showNewVertical && (
          <div className="rounded-md border border-primary/30 bg-secondary/50 p-4 space-y-3">
            <p className="text-xs font-medium">New Vertical</p>
            <div className="grid grid-cols-2 gap-3">
              <Input placeholder="Name" value={newVerticalName} onChange={(e) => setNewVerticalName(e.target.value)} />
              <Input placeholder="Code" value={newVerticalCode} onChange={(e) => setNewVerticalCode(e.target.value)} />
              <Input placeholder="Business objective" value={newVerticalObjective} onChange={(e) => setNewVerticalObjective(e.target.value)} />
              <Input placeholder="Primary KPI" value={newVerticalKpi} onChange={(e) => setNewVerticalKpi(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleAddVertical}>Add</Button>
              <Button size="sm" variant="outline" onClick={() => setShowNewVertical(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function FieldTile({
  label, value, onChange, multiline,
}: {
  label: string; value: string; onChange: (v: string) => void; multiline?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-foreground">{label}</label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
        />
      ) : (
        <Input value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}
