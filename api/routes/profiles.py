"""
Business Profile CRUD endpoints.

Handles creation, listing, updating, and deletion of brand profiles
and their verticals.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from crm_intelligence.models.profile import BusinessProfile, VerticalProfile
from crm_intelligence.storage import load_profile, save_profile

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response schemas (API-specific, decoupled from internal models)
# ---------------------------------------------------------------------------


class VerticalCreateRequest(BaseModel):
    """Request body for creating/updating a vertical."""

    name: str
    code: str
    business_objective: Optional[str] = None
    primary_kpi: Optional[str] = None
    typical_cta: Optional[str] = None
    target_audience: Optional[str] = None
    success_metrics: Optional[str] = None
    notes: Optional[str] = None


class ProfileCreateRequest(BaseModel):
    """Request body for creating a new brand profile."""

    # Essentials (required)
    company_name: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    description: Optional[str] = None
    crm_platform: Optional[str] = None  # "CleverTap", "MoEngage"

    # Enrichment (optional)
    business_model: Optional[str] = None
    brand_positioning: Optional[str] = None
    products_services: Optional[str] = None
    target_audience: Optional[str] = None
    website: Optional[str] = None
    marketing_strategy: Optional[str] = None
    communication_goals: Optional[str] = None
    retention_strategy: Optional[str] = None
    brand_voice: Optional[str] = None
    business_constraints: Optional[str] = None
    kpis: Optional[str] = None

    # Report configuration
    selected_sections: list[str] = Field(default_factory=list)
    ranking_metric: str = "composite"
    performers_count: int = 5
    offer_extraction_pattern: Optional[str] = None
    label_separator: str = "|"

    # Verticals (can be added during creation or later)
    verticals: list[VerticalCreateRequest] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    """Request body for updating an existing profile (all fields optional)."""

    industry: Optional[str] = None
    description: Optional[str] = None
    business_model: Optional[str] = None
    brand_positioning: Optional[str] = None
    products_services: Optional[str] = None
    target_audience: Optional[str] = None
    website: Optional[str] = None
    crm_platform: Optional[str] = None
    marketing_strategy: Optional[str] = None
    communication_goals: Optional[str] = None
    retention_strategy: Optional[str] = None
    brand_voice: Optional[str] = None
    business_constraints: Optional[str] = None
    kpis: Optional[str] = None
    selected_sections: Optional[list[str]] = None
    ranking_metric: Optional[str] = None
    performers_count: Optional[int] = None
    offer_extraction_pattern: Optional[str] = None
    label_separator: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper to list all profiles (scan storage directory)
# ---------------------------------------------------------------------------


def _list_all_profiles() -> list[BusinessProfile]:
    """Load all profiles from storage."""
    from pathlib import Path

    profiles_dir = Path("storage/profiles")
    if not profiles_dir.exists():
        return []

    profiles = []
    for f in profiles_dir.glob("*.json"):
        try:
            import json

            data = json.loads(f.read_text(encoding="utf-8"))
            profile = BusinessProfile(**data)
            profiles.append(profile)
        except Exception:
            continue
    return profiles


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_profiles():
    """List all brand profiles (summary view)."""
    profiles = _list_all_profiles()
    return {
        "profiles": [
            {
                "company_name": p.company_name,
                "industry": p.industry,
                "description": p.description,
                "verticals_count": len(p.verticals),
                "verticals": [{"name": v.name, "code": v.code} for v in p.verticals],
                "selected_sections": p.selected_sections,
                "created_at": p.created_at.isoformat(),
            }
            for p in profiles
        ]
    }


@router.get("/{company_name}")
async def get_profile(company_name: str):
    """Get full profile for a brand."""
    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")
    return profile.model_dump(mode="json")


@router.post("")
async def create_profile(request: ProfileCreateRequest):
    """Create a new brand profile."""
    # Check if profile already exists
    existing = load_profile(request.company_name)
    if existing is not None:
        raise HTTPException(
            status_code=409, detail=f"Profile already exists: {request.company_name}"
        )

    # Build verticals
    verticals = [
        VerticalProfile(
            name=v.name,
            code=v.code,
            business_objective=v.business_objective,
            primary_kpi=v.primary_kpi,
            typical_cta=v.typical_cta,
            target_audience=v.target_audience,
            success_metrics=v.success_metrics,
            notes=v.notes,
        )
        for v in request.verticals
    ]

    # Build profile
    profile = BusinessProfile(
        company_name=request.company_name,
        industry=request.industry,
        description=request.description,
        business_model=request.business_model,
        brand_positioning=request.brand_positioning,
        products_services=request.products_services,
        target_audience=request.target_audience,
        website=request.website,
        crm_platforms=[request.crm_platform] if request.crm_platform else [],
        marketing_strategy=request.marketing_strategy,
        communication_goals=request.communication_goals,
        retention_strategy=request.retention_strategy,
        brand_voice=request.brand_voice,
        business_constraints=request.business_constraints,
        kpis=request.kpis,
        selected_sections=request.selected_sections,
        ranking_metric=request.ranking_metric,
        performers_count=request.performers_count,
        offer_extraction_pattern=request.offer_extraction_pattern,
        label_separator=request.label_separator,
        verticals=verticals,
    )

    save_profile(profile)
    return {"status": "created", "company_name": profile.company_name}


@router.put("/{company_name}")
async def update_profile(company_name: str, request: ProfileUpdateRequest):
    """Update an existing brand profile (partial update)."""
    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")

    # Apply only provided fields
    update_data = request.model_dump(exclude_none=True)
    for field, value in update_data.items():
        if field == "crm_platform":
            # Special handling: crm_platforms is a list
            if value and value not in profile.crm_platforms:
                profile.crm_platforms.append(value)
        elif hasattr(profile, field):
            setattr(profile, field, value)

    profile.updated_at = datetime.now()
    save_profile(profile)
    return {"status": "updated", "company_name": company_name}


@router.delete("/{company_name}")
async def delete_profile(company_name: str):
    """Delete a brand profile."""
    from pathlib import Path

    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")

    # Delete the file
    slug = company_name.lower().replace(" ", "-").replace("'", "")
    filepath = Path("storage/profiles") / f"{slug}.json"
    if filepath.exists():
        filepath.unlink()

    return {"status": "deleted", "company_name": company_name}


# ---------------------------------------------------------------------------
# Vertical sub-endpoints
# ---------------------------------------------------------------------------


@router.post("/{company_name}/verticals")
async def add_vertical(company_name: str, request: VerticalCreateRequest):
    """Add a vertical to an existing profile."""
    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")

    # Check for duplicate code
    existing = profile.get_vertical(request.code)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Vertical '{request.code}' already exists"
        )

    vertical = VerticalProfile(
        name=request.name,
        code=request.code,
        business_objective=request.business_objective,
        primary_kpi=request.primary_kpi,
        typical_cta=request.typical_cta,
        target_audience=request.target_audience,
        success_metrics=request.success_metrics,
        notes=request.notes,
    )
    profile.verticals.append(vertical)
    profile.updated_at = datetime.now()
    save_profile(profile)

    return {"status": "added", "vertical_code": request.code}


@router.put("/{company_name}/verticals/{vertical_code}")
async def update_vertical(
    company_name: str, vertical_code: str, request: VerticalCreateRequest
):
    """Update an existing vertical."""
    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")

    vertical = profile.get_vertical(vertical_code)
    if vertical is None:
        raise HTTPException(
            status_code=404, detail=f"Vertical not found: {vertical_code}"
        )

    # Update fields
    vertical.name = request.name
    vertical.code = request.code
    vertical.business_objective = request.business_objective
    vertical.primary_kpi = request.primary_kpi
    vertical.typical_cta = request.typical_cta
    vertical.target_audience = request.target_audience
    vertical.success_metrics = request.success_metrics
    vertical.notes = request.notes
    vertical.updated_at = datetime.now()

    profile.updated_at = datetime.now()
    save_profile(profile)

    return {"status": "updated", "vertical_code": vertical_code}


@router.delete("/{company_name}/verticals/{vertical_code}")
async def delete_vertical(company_name: str, vertical_code: str):
    """Remove a vertical from a profile."""
    profile = load_profile(company_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {company_name}")

    original_count = len(profile.verticals)
    profile.verticals = [
        v for v in profile.verticals if v.code.upper() != vertical_code.upper()
    ]

    if len(profile.verticals) == original_count:
        raise HTTPException(
            status_code=404, detail=f"Vertical not found: {vertical_code}"
        )

    profile.updated_at = datetime.now()
    save_profile(profile)

    return {"status": "deleted", "vertical_code": vertical_code}
