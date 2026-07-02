"""
Canonical Campaign model.

This is the internal representation of a single campaign row.
All platform adapters (CleverTap, MoEngage, etc.) MUST produce this format.
The analytics layer consumes ONLY this format — it never sees raw platform data.

Design principles:
- All numeric fields are concrete types (int/float), never strings.
- Date and time are proper types, never raw strings.
- This model IS the Data Contract. If an adapter can't produce it, it fails.
- Optional fields are truly optional (analysis works without them, just less rich).
"""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CanonicalCampaign(BaseModel):
    """
    One campaign row in canonical (platform-agnostic) format.

    Required fields represent the minimum viable data for meaningful analysis.
    Optional fields enrich analysis when present.
    """

    # --- Identity ---
    campaign_name: str = Field(description="Full campaign name as it appears in the export")
    channel: str = Field(description="Standardized channel: 'WhatsApp', 'Push Notification', 'RCS', 'Email', 'SMS'")
    segment: str = Field(description="Target segment name")

    # --- Timing ---
    start_date: date = Field(description="Campaign send date (ISO format)")
    start_time: time = Field(description="Campaign send time (24h format)")

    # --- Volume Metrics (required — analysis is impossible without these) ---
    estimated_reach: int = Field(ge=0, description="Target audience size")
    sent: int = Field(ge=0, description="Total users the campaign was sent to")
    delivered: int = Field(ge=0, description="Total users who received the campaign")
    viewed: int = Field(ge=0, description="Total users who viewed/opened the campaign")
    clicked: int = Field(ge=0, description="Total users who clicked")

    # --- Conversion Metrics (required for KPI analysis) ---
    click_conversions: int = Field(ge=0, description="Direct click-through conversions")
    influenced_conversions: int = Field(ge=0, description="Influenced/attributed conversions")

    # --- Content (required for creative intelligence) ---
    message: str = Field(min_length=1, description="Full message body text")

    # --- Optional Enrichment ---
    title: Optional[str] = Field(
        default=None,
        description="Campaign title/header (Push has this; WhatsApp often doesn't)",
    )
    labels: Optional[str] = Field(
        default=None,
        description="Campaign tags/labels (pipe-separated, e.g., 'eoss|jeans|sale')",
    )
    click_conversion_percent: Optional[float] = Field(
        default=None, ge=0, description="Click conversion rate (if provided by platform)"
    )
    influenced_conversion_percent: Optional[float] = Field(
        default=None, ge=0, description="Influenced conversion rate (if provided by platform)"
    )
    revenue: Optional[float] = Field(
        default=None, ge=0, description="Revenue attributed to this campaign"
    )
    errors: Optional[int] = Field(
        default=None, ge=0, description="Delivery errors/failures"
    )
    device: Optional[str] = Field(
        default=None, description="Target device type"
    )

    # --- Validation ---

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        """Ensure channel is one of the recognized standardized values."""
        allowed = {"WhatsApp", "Push Notification", "RCS", "Email", "SMS"}
        if v not in allowed:
            raise ValueError(
                f"Channel must be one of {allowed}, got '{v}'. "
                f"The platform adapter should standardize this before creating the model."
            )
        return v

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Ensure message has actual content (not just whitespace)."""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace-only.")
        return v
