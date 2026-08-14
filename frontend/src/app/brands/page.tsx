"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Building2, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { listProfiles, deleteProfile, type ProfileSummary } from "@/lib/api";

export default function BrandsPage() {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const loadProfiles = () => {
    listProfiles()
      .then((res) => setProfiles(res.profiles))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadProfiles(); }, []);

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await deleteProfile(name);
      loadProfiles();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="p-6 max-w-[900px] mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Brands</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage brand profiles and verticals
          </p>
        </div>
        <Link href="/brands/new">
          <Button size="sm">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            New Brand
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 bg-secondary rounded-md animate-pulse" />
          ))}
        </div>
      ) : profiles.length === 0 ? (
        <div className="text-center py-16">
          <Building2 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground mb-4">No brand profiles yet</p>
          <Link href="/brands/new">
            <Button size="sm">Create Brand</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {profiles.map((profile) => (
            <div
              key={profile.company_name}
              className="flex items-center justify-between rounded-md border border-border px-4 py-3 hover:bg-secondary/30 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-secondary shrink-0">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{profile.company_name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-2xs text-muted-foreground">{profile.industry}</span>
                    {profile.verticals.length > 0 && (
                      <div className="flex gap-1">
                        {profile.verticals.map((v) => (
                          <Badge key={v.code} variant="secondary">{v.name}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Link href={`/brands/${encodeURIComponent(profile.company_name)}`}>
                  <Button variant="ghost" size="sm" className="h-8">
                    <Pencil className="h-3.5 w-3.5 mr-1.5" />
                    Edit
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-muted-foreground hover:text-destructive"
                  onClick={() => handleDelete(profile.company_name)}
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
