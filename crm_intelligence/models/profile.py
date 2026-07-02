"""
Business Profile and Vertical Profile models.

These represent the persistent knowledge about a client business.
Created once during onboarding, enriched progressively through observations.

Design principles:
- Required fields are ONLY those the system cannot function without.
- Everything else is optional — empty fields degrade insight quality gracefully,
  but never block analysis.
- Observations are append-only (accumulated from analysis runs).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VerticalProfile(BaseModel):
    """
    A business vertical (e.g., HFRP, Occupancy, ASF).

    Each vertical has its own objectives, KPIs, and context.
    When a report is generated for a vertical, this profile is injected
    into the LLM context so insights are business-specific.
    """

    # --- Required ---
    name: str = Field(description="Vertical name (e.g., 'HFRP', 'Occupancy', 'ASF')")
    code: str = Field(description="Short code used in campaign names (e.g., 'HFRP', 'OCC', 'ASF')")

    # --- Business Context (optional but valuable) ---
    business_objective: Optional[str] = Field(
        default=None,
        description="What this vertical aims to achieve (e.g., 'Generate qualified referrals')",
    )
    primary_kpi: Optional[str] = Field(
        default=None,
        description="The single most important metric (e.g., 'Referral Submitted')",
    )
    typical_cta: Optional[str] = Field(
        default=None,
        description="Common call-to-action used (e.g., 'Refer Now')",
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Who this vertical targets (e.g., 'Active members with 6+ month tenure')",
    )
    success_metrics: Optional[str] = Field(
        default=None,
        description="How success is measured beyond primary KPI",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Any additional context for this vertical",
    )

    # --- Metadata ---
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("success_metrics", "target_audience", mode="before")
    @classmethod
    def _coerce_list_to_str(cls, v):
        """Accept a JSON array and join it into a comma-separated string."""
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)
        return v


class Observation(BaseModel):
    """
    A learned fact about the business that emerged during analysis.

    Observations are accumulated over time and injected into LLM context
    so the system never re-asks or re-mistakes something it already learned.

    Examples:
    - "Meta Marketing templates have ~50% delivery — this is observed behavior, not a bug"
    - "Push Notification uses Total Viewed as delivered proxy (Total Delivered is always 0)"
    - "Urgency countdown only effective within 72 hours"
    """

    content: str = Field(description="The observation itself")
    category: str = Field(
        description="Type: 'data_quirk' | 'business_rule' | 'pattern' | 'correction'"
    )
    source: Optional[str] = Field(
        default=None,
        description="How this was discovered (e.g., 'May 2026 analysis', 'user correction')",
    )
    created_at: datetime = Field(default_factory=datetime.now)


class BusinessProfile(BaseModel):
    """
    The complete knowledge about a client business.

    Created once during onboarding. The structured fields drive analytics
    and report generation. Observations accumulate from each analysis run.

    This is the single most important object in the system — it's what
    makes the difference between generic AI output and business-specific intelligence.
    """

    # --- Required (system cannot function without these) ---
    company_name: str = Field(description="Legal or brand name of the company")
    industry: str = Field(description="Industry vertical (e.g., 'Travel & Hospitality')")

    # --- Business Identity (valuable for LLM context) ---
    business_model: Optional[str] = Field(
        default=None,
        description="How the business makes money (e.g., 'B2C Membership / Vacation Ownership')",
    )
    description: Optional[str] = Field(
        default=None,
        description="What the company does, who it serves, what problem it solves",
    )
    brand_positioning: Optional[str] = Field(
        default=None,
        description="Brand themes (e.g., 'family vacations, togetherness, premium experiences')",
    )
    products_services: Optional[str] = Field(
        default=None,
        description="Key products/services offered",
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Who the company's customers are",
    )
    website: Optional[str] = Field(default=None, description="Company website URL")

    # --- Marketing Context ---
    crm_platforms: list[str] = Field(
        default_factory=list,
        description="CRM/marketing platforms in use (e.g., ['CleverTap', 'MoEngage'])",
    )
    marketing_strategy: Optional[str] = Field(
        default=None,
        description="High-level marketing approach and priorities",
    )
    communication_goals: Optional[str] = Field(
        default=None,
        description="What the CRM communication aims to achieve",
    )
    retention_strategy: Optional[str] = Field(
        default=None,
        description="How the business retains customers",
    )
    brand_voice: Optional[str] = Field(
        default=None,
        description="Tone and style of communications (e.g., 'warm, family-oriented, premium')",
    )

    # --- Business Constraints ---
    business_constraints: Optional[str] = Field(
        default=None,
        description="Known limitations (e.g., 'No revenue tracking — members pre-paid')",
    )
    kpis: Optional[str] = Field(
        default=None,
        description="Key business KPIs that CRM campaigns drive",
    )

    # --- Report Configuration ---
    selected_sections: list[str] = Field(
        default_factory=list,
        description=(
            "Report sections this brand wants. "
            "If empty, defaults are computed from vertical + data shape. "
            "Values: performers, timing, recommendations, channel_performance, "
            "offer_analysis, label_analysis, creative_intelligence, keywords, "
            "emoji, message_structure"
        ),
    )
    ranking_metric: str = Field(
        default="composite",
        description="How to rank campaigns: 'composite' (40% CTR + 30% CTOR + 30% CVR), 'ctr', 'ctor'",
    )
    performers_count: int = Field(
        default=5,
        description="Number of top/bottom performers to show",
    )
    offer_extraction_pattern: Optional[str] = Field(
        default=None,
        description=(
            "Campaign naming pattern for offer extraction. "
            "e.g., 'PROGRAM_CHANNEL_OFFER_DATE' for Club Mahindra. "
            "None means no automated offer extraction."
        ),
    )
    label_separator: Optional[str] = Field(
        default="|",
        description="Separator for multi-value labels (e.g., '|' for 'eoss|jeans')",
    )

    # --- Validators (accept list or string for flexible JSON authoring) ---

    @field_validator("products_services", "kpis", "target_audience", mode="before")
    @classmethod
    def _coerce_list_to_str(cls, v):
        """Accept a JSON array and join it into a comma-separated string."""
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)
        return v

    @field_validator("observations", mode="before")
    @classmethod
    def _coerce_observations(cls, v):
        """Accept plain strings and wrap them as Observation objects."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"content": item, "category": "business_rule"})
            else:
                result.append(item)
        return result

    # --- Verticals ---
    verticals: list[VerticalProfile] = Field(
        default_factory=list,
        description="Business verticals (HFRP, Occupancy, etc.)",
    )

    # --- Accumulated Knowledge ---
    observations: list[Observation] = Field(
        default_factory=list,
        description="Learned facts from analysis runs (grows over time)",
    )

    # --- Metadata ---
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_vertical(self, code: str) -> Optional[VerticalProfile]:
        """Look up a vertical by its code (case-insensitive)."""
        code_upper = code.upper()
        for vertical in self.verticals:
            if vertical.code.upper() == code_upper:
                return vertical
        return None

    def get_observations_text(self) -> str:
        """Format all observations as a single text block for LLM context injection."""
        if not self.observations:
            return ""
        lines = []
        for obs in self.observations:
            lines.append(f"- [{obs.category}] {obs.content}")
        return "\n".join(lines)
