"""
Analytics Engine — deterministic computation of all metrics and aggregations.

This module is the BRAIN of the analytics layer. It takes a list of
CanonicalCampaign objects (from any adapter) and produces a complete
Facts object containing:

1. Overall metrics (dataset-wide totals and rates)
2. Channel aggregation (metrics grouped by channel)
3. Offer aggregation (metrics grouped by extracted offer type)
4. Segment aggregation (metrics grouped by audience segment)
5. Day-of-week aggregation (metrics grouped by day name)
6. Hour-of-day aggregation (metrics grouped by hour bucket)
7. Top/bottom performer rankings (composite CTR + CTOR + conversions score)
8. Analysis metadata (date range, counts, timestamp)

Principle: EVERY number in Facts is computed here, deterministically.
The LLM never computes — it only classifies and narrates.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

from crm_intelligence.config import RANKING_TOP_N
from crm_intelligence.models.campaign import CanonicalCampaign
from crm_intelligence.models.facts import (
    AnalysisMeta,
    CampaignHighlight,
    ChannelMetrics,
    Facts,
    LabelMetrics,
    OfferMetrics,
    OverallMetrics,
    SegmentMetrics,
    TimingMetrics,
    TrendComparison,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate computation helpers (safe division, never NaN)
# ---------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float:
    """Compute a percentage rate, returning 0.0 if denominator is 0."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _composite_score(campaign: CanonicalCampaign) -> float:
    """
    Composite performance score for ranking.

    Combines CTR (40%), CTOR (30%), and influenced conversion rate (30%).
    This ensures campaigns are ranked by engagement quality + business impact,
    not just raw click volume.

    Returns a 0-100 score (higher = better performer).
    """
    ctr = _rate(campaign.clicked, campaign.sent)
    ctor = _rate(campaign.clicked, campaign.viewed) if campaign.viewed > 0 else 0.0
    cvr = _rate(campaign.influenced_conversions, campaign.sent)

    # Weighted composite (weights sum to 1.0)
    return round(0.4 * ctr + 0.3 * ctor + 0.3 * cvr, 4)


# ---------------------------------------------------------------------------
# Offer Extraction (deterministic pattern matching from campaign names)
# ---------------------------------------------------------------------------

# Common offer patterns found in CRM campaign naming conventions:
# - "HFRP_WA_2Nights_17052026" → "2 Nights"
# - "HFRP_PN_BrandVoucher_20052026" → "Brand Voucher"
# - "HFRP_WA_ResortBillZero_03052026" → "Resort Bill Zero"
# - "HFRP_WA_Anniversary_28052026" → "Anniversary"
# - "HFRP_RCS_ASFCrossSell_23052026" → "ASF Cross Sell"

# Strategy: extract the third segment from underscore-delimited names,
# then CamelCase-split and clean it.

# Known offer types (direct map for precision)
_KNOWN_OFFERS = {
    "2nights": "2 Nights Stay",
    "4nights": "4 Nights Stay",
    "anniversary": "Anniversary",
    "birthday": "Birthday",
    "brandvoucher": "Brand Voucher",
    "resortbillzero": "Resort Bill Zero",
    "asfcrosssell": "ASF Cross Sell",
}


def extract_offer(campaign_name: str) -> str:
    """
    Extract the offer type from a campaign name.

    Uses a two-pass strategy:
    1. Try structured name pattern: PREFIX_CHANNEL_OFFER_DATE
    2. If no match, return "General" as fallback.

    Returns a human-readable offer label.
    """
    parts = campaign_name.split("_")

    # Pattern: PREFIX_CHANNEL_OFFER_DATE (at least 4 parts)
    if len(parts) >= 4:
        # Offer is the third part (index 2), possibly with number prefix
        offer_raw = parts[2]

        # Check known offers (case-insensitive)
        offer_key = offer_raw.lower()
        if offer_key in _KNOWN_OFFERS:
            return _KNOWN_OFFERS[offer_key]

        # CamelCase split: "BrandVoucher" → "Brand Voucher"
        split = re.sub(r"([a-z])([A-Z])", r"\1 \2", offer_raw)
        # Number prefix: "2Nights" → "2 Nights"
        split = re.sub(r"(\d+)([A-Z])", r"\1 \2", split)

        if split.strip():
            return split.strip()

    # Pattern 2: Check if any known keyword appears anywhere in the name
    name_lower = campaign_name.lower().replace("_", "").replace(" ", "")
    for key, label in _KNOWN_OFFERS.items():
        if key in name_lower:
            return label

    return "General"


# ---------------------------------------------------------------------------
# Hour bucketing
# ---------------------------------------------------------------------------

# 4-hour buckets: more useful for strategic timing decisions than raw hours
_HOUR_BUCKETS = [
    (0, 6, "00-06 (Night)"),
    (6, 9, "06-09 (Early Morning)"),
    (9, 12, "09-12 (Morning)"),
    (12, 15, "12-15 (Afternoon)"),
    (15, 18, "15-18 (Evening)"),
    (18, 21, "18-21 (Prime Time)"),
    (21, 24, "21-24 (Late Night)"),
]


def _get_hour_bucket(hour: int) -> str:
    """Get the time bucket label for an hour (0-23)."""
    for start, end, label in _HOUR_BUCKETS:
        if start <= hour < end:
            return label
    return "Unknown"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


class _Accumulator:
    """Accumulates raw counts for a group, then computes rates."""

    def __init__(self):
        self.campaign_count = 0
        self.total_sent = 0
        self.total_delivered = 0
        self.total_viewed = 0
        self.total_clicked = 0
        self.total_click_conversions = 0
        self.total_influenced_conversions = 0
        self.total_errors = 0
        self.total_estimated_reach = 0

    def add(self, c: CanonicalCampaign) -> None:
        """Add a campaign's numbers to this accumulator."""
        self.campaign_count += 1
        self.total_sent += c.sent
        self.total_delivered += c.delivered
        self.total_viewed += c.viewed
        self.total_clicked += c.clicked
        self.total_click_conversions += c.click_conversions
        self.total_influenced_conversions += c.influenced_conversions
        self.total_errors += c.errors if c.errors else 0
        self.total_estimated_reach += c.estimated_reach

    @property
    def ctr(self) -> float:
        return _rate(self.total_clicked, self.total_sent)

    @property
    def ctor(self) -> float:
        return _rate(self.total_clicked, self.total_viewed)

    @property
    def delivery_rate(self) -> float:
        return _rate(self.total_delivered, self.total_sent)

    @property
    def error_rate(self) -> Optional[float]:
        if self.total_estimated_reach == 0:
            return None
        return _rate(self.total_errors, self.total_estimated_reach)

    @property
    def cvr_click(self) -> float:
        return _rate(self.total_click_conversions, self.total_sent)

    @property
    def cvr_influenced(self) -> float:
        return _rate(self.total_influenced_conversions, self.total_sent)


# ---------------------------------------------------------------------------
# Main computation entry point
# ---------------------------------------------------------------------------


def compute_facts(
    campaigns: list[CanonicalCampaign],
    company: str,
    vertical: str,
    prior_facts: Optional[Facts] = None,
    selected_sections: Optional[list[str]] = None,
    label_separator: str = "|",
) -> Facts:
    """
    Compute the complete Facts object from a list of campaigns.

    This is the single entry point for all deterministic analytics.
    No LLM calls happen here. Every number is reproducible.

    Args:
        campaigns: List of validated CanonicalCampaign objects (from adapter).
        company: Company name (for metadata).
        vertical: Vertical code/name (for metadata).
        prior_facts: Optional prior run's Facts (for trend comparison).
        selected_sections: List of section IDs the user selected. If None,
            all sections are computed (backward-compatible default).
        label_separator: Separator for multi-value labels (default "|").

    Returns:
        A complete Facts object ready for LLM narration and DOCX rendering.

    Raises:
        ValueError: If campaigns list is empty.
    """
    if not campaigns:
        raise ValueError("Cannot compute facts from an empty campaign list.")

    # If no sections specified, compute everything (backward compat)
    sections = set(selected_sections) if selected_sections else None

    logger.info(f"Computing facts for {len(campaigns)} campaigns ({company} / {vertical})")

    # --- Step 1: Overall metrics ---
    overall_acc = _Accumulator()
    for c in campaigns:
        overall_acc.add(c)

    overall = OverallMetrics(
        total_campaigns=overall_acc.campaign_count,
        total_sent=overall_acc.total_sent,
        total_delivered=overall_acc.total_delivered,
        total_viewed=overall_acc.total_viewed,
        total_clicked=overall_acc.total_clicked,
        total_click_conversions=overall_acc.total_click_conversions,
        total_influenced_conversions=overall_acc.total_influenced_conversions,
        overall_ctr=overall_acc.ctr,
        overall_ctor=overall_acc.ctor,
        overall_delivery_rate=overall_acc.delivery_rate,
        overall_cvr_click=overall_acc.cvr_click,
        overall_cvr_influenced=overall_acc.cvr_influenced,
        overall_error_rate=overall_acc.error_rate,
    )

    # --- Step 2: Aggregate by channel (skip if only 1 channel or not selected) ---
    by_channel = []
    if sections is None or "channel_performance" in sections:
        channel_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
        for c in campaigns:
            channel_groups[c.channel].add(c)

        by_channel = [
            ChannelMetrics(
                channel=ch,
                campaign_count=acc.campaign_count,
                total_sent=acc.total_sent,
                total_delivered=acc.total_delivered,
                total_viewed=acc.total_viewed,
                total_clicked=acc.total_clicked,
                total_click_conversions=acc.total_click_conversions,
                total_influenced_conversions=acc.total_influenced_conversions,
                ctr=acc.ctr,
                ctor=acc.ctor,
                delivery_rate=acc.delivery_rate,
                error_rate=acc.error_rate,
                cvr_influenced=acc.cvr_influenced,
            )
            for ch, acc in sorted(channel_groups.items(), key=lambda x: x[1].total_sent, reverse=True)
        ]

    # --- Step 3: Aggregate by offer type (skip if not selected) ---
    by_offer = []
    if sections is None or "offer_analysis" in sections:
        offer_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
        for c in campaigns:
            offer = extract_offer(c.campaign_name)
            offer_groups[offer].add(c)

        by_offer = [
            OfferMetrics(
                offer=offer,
                campaign_count=acc.campaign_count,
                total_sent=acc.total_sent,
                total_clicked=acc.total_clicked,
                total_influenced_conversions=acc.total_influenced_conversions,
                ctr=acc.ctr,
                ctor=acc.ctor,
                cvr_influenced=acc.cvr_influenced,
            )
            for offer, acc in sorted(offer_groups.items(), key=lambda x: x[1].cvr_influenced, reverse=True)
        ]

    # --- Step 3b: Aggregate by label/tag (skip if not selected) ---
    by_label = []
    if sections is None or "label_analysis" in sections:
        label_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
        for c in campaigns:
            # Labels can be multi-value (pipe-separated)
            labels_raw = getattr(c, "labels", "") or ""
            if labels_raw:
                for label in labels_raw.split(label_separator):
                    label = label.strip()
                    if label and label.lower() not in ("n/a", "nan", "none"):
                        label_groups[label].add(c)

        by_label = [
            LabelMetrics(
                label=label,
                campaign_count=acc.campaign_count,
                total_sent=acc.total_sent,
                total_viewed=acc.total_viewed,
                total_clicked=acc.total_clicked,
                total_influenced_conversions=acc.total_influenced_conversions,
                ctr=acc.ctr,
                ctor=acc.ctor,
                viewed_pct=_rate(acc.total_viewed, acc.total_sent),
            )
            for label, acc in sorted(label_groups.items(), key=lambda x: x[1].ctr, reverse=True)
            if acc.campaign_count >= 2  # Only labels with 2+ campaigns
        ]

    # --- Step 4: Aggregate by segment ---
    by_segment = []
    segment_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
    for c in campaigns:
        segment_groups[c.segment].add(c)

    by_segment = [
        SegmentMetrics(
            segment=seg,
            campaign_count=acc.campaign_count,
            total_sent=acc.total_sent,
            total_clicked=acc.total_clicked,
            total_influenced_conversions=acc.total_influenced_conversions,
            ctr=acc.ctr,
            ctor=acc.ctor,
        )
        for seg, acc in sorted(segment_groups.items(), key=lambda x: x[1].ctr, reverse=True)
    ]

    # --- Step 5: Aggregate by day of week ---
    day_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
    for c in campaigns:
        day_name = c.start_date.strftime("%A")  # "Monday", "Tuesday", etc.
        day_groups[day_name].add(c)

    # Sort by day order (Mon-Sun), not alphabetical
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = [
        TimingMetrics(
            bucket=day,
            campaign_count=acc.campaign_count,
            total_sent=acc.total_sent,
            total_clicked=acc.total_clicked,
            total_influenced_conversions=acc.total_influenced_conversions,
            ctr=acc.ctr,
            ctor=acc.ctor,
        )
        for day in day_order
        if (acc := day_groups.get(day)) is not None
    ]

    # --- Step 6: Aggregate by hour bucket ---
    hour_groups: dict[str, _Accumulator] = defaultdict(_Accumulator)
    for c in campaigns:
        bucket = _get_hour_bucket(c.start_time.hour)
        hour_groups[bucket].add(c)

    # Sort by bucket order (chronological)
    bucket_order = [label for _, _, label in _HOUR_BUCKETS]
    by_hour = [
        TimingMetrics(
            bucket=bucket,
            campaign_count=acc.campaign_count,
            total_sent=acc.total_sent,
            total_clicked=acc.total_clicked,
            total_influenced_conversions=acc.total_influenced_conversions,
            ctr=acc.ctr,
            ctor=acc.ctor,
        )
        for bucket in bucket_order
        if (acc := hour_groups.get(bucket)) is not None
    ]

    # --- Step 7: Top/Bottom performers ---
    # Sort all campaigns by composite score
    scored = sorted(campaigns, key=_composite_score, reverse=True)

    top_n = min(RANKING_TOP_N, len(scored))

    def _to_highlight(c: CanonicalCampaign) -> CampaignHighlight:
        return CampaignHighlight(
            campaign_name=c.campaign_name,
            channel=c.channel,
            segment=c.segment,
            offer=extract_offer(c.campaign_name),
            ctr=_rate(c.clicked, c.sent),
            ctor=_rate(c.clicked, c.viewed) if c.viewed > 0 else 0.0,
            click_conversions=c.click_conversions,
            influenced_conversions=c.influenced_conversions,
            sent=c.sent,
            message=c.message,
            title=c.title,
        )

    top_performers = [_to_highlight(c) for c in scored[:top_n]]
    bottom_performers = [_to_highlight(c) for c in scored[-top_n:]]
    # Reverse bottom so worst is first
    bottom_performers.reverse()

    # --- Step 8: Metadata ---
    dates = sorted(c.start_date for c in campaigns)
    channels = sorted(set(c.channel for c in campaigns))

    meta = AnalysisMeta(
        company=company,
        vertical=vertical,
        date_range_start=dates[0],
        date_range_end=dates[-1],
        campaign_count=len(campaigns),
        channels=channels,
        total_sent=overall_acc.total_sent,
        run_timestamp=datetime.now().isoformat(),
    )

    # --- Step 9: Trend comparison (if prior facts provided) ---
    comparison = None
    if prior_facts is not None:
        try:
            ctr_delta = round(overall.overall_ctr - prior_facts.overall.overall_ctr, 2)
            conv_delta = (
                overall.total_influenced_conversions
                - prior_facts.overall.total_influenced_conversions
            )
            comparison = TrendComparison(
                vs_period=f"{prior_facts.meta.date_range_start.strftime('%B %Y')}",
                ctr_delta=ctr_delta,
                conversion_delta=conv_delta,
            )
        except Exception as e:
            logger.warning(f"Could not compute trend comparison: {e}")

    # --- Assemble the Facts ---
    facts = Facts(
        meta=meta,
        overall=overall,
        by_channel=by_channel,
        by_offer=by_offer,
        by_segment=by_segment,
        by_day=by_day,
        by_hour=by_hour,
        # LLM-classified fields left empty — populated after L1
        by_opening_style=[],
        by_tone=[],
        by_headline_quality=[],
        by_cta_strength=[],
        by_emoji_bucket=[],
        by_label=by_label,
        top_performers=top_performers,
        bottom_performers=bottom_performers,
        comparison=comparison,
    )

    logger.info(
        f"Facts computed: {overall.total_campaigns} campaigns, "
        f"{len(by_channel)} channels, {len(by_offer)} offers, "
        f"{len(by_label)} labels, {len(by_segment)} segments, "
        f"{len(by_day)} days, {len(by_hour)} hour buckets"
    )

    return facts
