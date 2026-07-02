"""
Facts schema — the complete computed truth.

facts.json is the HINGE of the entire system:
- Deterministic code PRODUCES it (analytics layer)
- The LLM CONSUMES it (narration layer)
- The renderer DRAWS from it (tables in the DOCX)

The LLM never sees raw campaign data for computation purposes.
It only sees this pre-computed, verified structure.

Design principles:
- Every number here is deterministic and reproducible.
- The schema is self-describing (an analyst can read facts.json and understand it without docs).
- Aggregation groups use lists (not dicts) so they're ordered and indexable.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# --- Aggregation Group Models ---


class ChannelMetrics(BaseModel):
    """Aggregated metrics for one channel."""

    channel: str
    campaign_count: int
    total_sent: int
    total_delivered: int
    total_viewed: int
    total_clicked: int
    total_click_conversions: int
    total_influenced_conversions: int
    ctr: float = Field(description="Click-through rate: clicked/sent * 100")
    ctor: float = Field(description="Click-to-open rate: clicked/viewed * 100")
    delivery_rate: float = Field(description="delivered/sent * 100")
    error_rate: Optional[float] = Field(default=None, description="errors/estimated_reach * 100")
    cvr_influenced: float = Field(description="influenced_conversions/sent * 100")


class OfferMetrics(BaseModel):
    """Aggregated metrics for one offer type."""

    offer: str
    campaign_count: int
    total_sent: int
    total_clicked: int
    total_influenced_conversions: int
    ctr: float
    ctor: float
    cvr_influenced: float


class SegmentMetrics(BaseModel):
    """Aggregated metrics for one audience segment."""

    segment: str
    campaign_count: int
    total_sent: int
    total_clicked: int
    total_influenced_conversions: int
    ctr: float
    ctor: float


class TimingMetrics(BaseModel):
    """Aggregated metrics for one time bucket."""

    bucket: str = Field(description="Day name or hour range (e.g., 'Monday', '12-15')")
    campaign_count: int
    total_sent: int
    total_clicked: int
    total_influenced_conversions: int
    ctr: float
    ctor: float


class ClassificationMetrics(BaseModel):
    """Aggregated metrics for one LLM-classified dimension."""

    label: str = Field(description="The classification label (e.g., 'emotional', 'urgency')")
    campaign_count: int
    ctr: float
    ctor: float
    total_influenced_conversions: int


class KeywordMetrics(BaseModel):
    """Aggregated metrics for one keyword theme across all campaigns that contain it."""

    keyword: str
    campaign_count: int
    total_sent: int
    total_clicked: int
    total_influenced_conversions: int
    ctr: float
    ctor: float


class LabelMetrics(BaseModel):
    """Aggregated metrics for one campaign label/tag (e.g., 'eoss', 'jeans', 'payday')."""

    label: str
    campaign_count: int
    total_sent: int
    total_viewed: int
    total_clicked: int
    total_influenced_conversions: int
    ctr: float
    ctor: float
    viewed_pct: float = Field(description="Viewed / Sent * 100")


class CampaignHighlight(BaseModel):
    """A single campaign highlighted as top or bottom performer."""

    campaign_name: str
    channel: str
    segment: str
    offer: Optional[str] = None
    ctr: float
    ctor: float
    click_conversions: int
    influenced_conversions: int
    sent: int
    message: str = Field(description="Full message text (for creative analysis by LLM)")
    title: Optional[str] = None


# --- The Complete Facts Object ---


class AnalysisMeta(BaseModel):
    """Metadata about this analysis run."""

    company: str
    vertical: str
    date_range_start: date
    date_range_end: date
    campaign_count: int
    channels: list[str]
    total_sent: int
    run_timestamp: str


class OverallMetrics(BaseModel):
    """Dataset-wide totals and weighted averages."""

    total_campaigns: int
    total_sent: int
    total_delivered: int
    total_viewed: int
    total_clicked: int
    total_click_conversions: int
    total_influenced_conversions: int
    overall_ctr: float
    overall_ctor: float
    overall_delivery_rate: float
    overall_cvr_click: float
    overall_cvr_influenced: float
    overall_error_rate: Optional[float] = None


class TrendComparison(BaseModel):
    """Month-over-month comparison (when historical data exists)."""

    vs_period: str = Field(description="What we're comparing against (e.g., 'April 2026')")
    ctr_delta: float = Field(description="Change in CTR (percentage points)")
    conversion_delta: int = Field(description="Change in total influenced conversions")
    notes: Optional[str] = None


class Facts(BaseModel):
    """
    The complete computed truth for one analysis run.

    This is the single object that:
    - Analytics code produces (deterministically)
    - The LLM narrates from (it cannot alter these numbers)
    - The DOCX renderer draws tables from

    Every number here is independently verifiable by re-running the analytics code.
    """

    meta: AnalysisMeta
    overall: OverallMetrics

    # --- Grouped aggregations ---
    by_channel: list[ChannelMetrics]
    by_offer: list[OfferMetrics]
    by_segment: list[SegmentMetrics]
    by_day: list[TimingMetrics]
    by_hour: list[TimingMetrics]

    # --- LLM-classified dimensions (populated after classification step) ---
    by_opening_style: list[ClassificationMetrics] = Field(default_factory=list)
    by_tone: list[ClassificationMetrics] = Field(default_factory=list)
    by_headline_quality: list[ClassificationMetrics] = Field(default_factory=list)
    by_cta_strength: list[ClassificationMetrics] = Field(default_factory=list)
    by_emoji_bucket: list[ClassificationMetrics] = Field(default_factory=list)
    by_keyword: list[KeywordMetrics] = Field(default_factory=list)
    by_message_structure: list[ClassificationMetrics] = Field(default_factory=list)
    by_message_length: list[ClassificationMetrics] = Field(default_factory=list)

    # --- Label/tag aggregation (for brands using Labels column) ---
    by_label: list["LabelMetrics"] = Field(default_factory=list)

    # --- Rankings ---
    top_performers: list[CampaignHighlight]
    bottom_performers: list[CampaignHighlight]

    # --- Historical comparison (optional) ---
    comparison: Optional[TrendComparison] = None
