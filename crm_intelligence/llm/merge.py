"""
Classification merger — integrates L1 classification results back into Facts.

After classify_campaigns() produces labels for each campaign, this module
computes the aggregated metrics (by_opening_style, by_tone, etc.) and
updates the Facts object with those grouped classifications.

This keeps the aggregation logic in deterministic Python code,
not in the LLM — maintaining the principle that LLM classifies,
code computes.
"""

import logging
from collections import defaultdict

from crm_intelligence.analytics.engine import _rate
from crm_intelligence.llm.classifier import CampaignClassification
from crm_intelligence.models.campaign import CanonicalCampaign
from crm_intelligence.models.facts import ClassificationMetrics, KeywordMetrics, Facts

logger = logging.getLogger(__name__)


def merge_classifications(
    facts: Facts,
    campaigns: list[CanonicalCampaign],
    classifications: list[CampaignClassification],
) -> Facts:
    """
    Merge LLM classification results into the Facts object.

    Computes aggregated metrics for each classification dimension
    (opening_style, tone, headline_quality, cta_strength, emoji_bucket)
    and updates the Facts model's corresponding fields.

    Args:
        facts: The Facts object to update (from compute_facts).
        campaigns: The campaign list (same order as classifications).
        classifications: L1 classification results (same order as campaigns).

    Returns:
        Updated Facts with classification aggregations populated.
    """
    if len(campaigns) != len(classifications):
        logger.warning(
            f"Campaign count ({len(campaigns)}) != classification count "
            f"({len(classifications)}). Matching by index."
        )

    # Pair campaigns with their classifications
    pairs = list(zip(campaigns, classifications))

    # Aggregate each dimension
    facts.by_opening_style = _aggregate_dimension(pairs, "opening_style")
    facts.by_tone = _aggregate_dimension(pairs, "tone")
    facts.by_headline_quality = _aggregate_dimension(pairs, "headline_quality")
    facts.by_cta_strength = _aggregate_dimension(pairs, "cta_strength")
    facts.by_emoji_bucket = _aggregate_dimension(pairs, "emoji_bucket")
    facts.by_message_structure = _aggregate_dimension(pairs, "message_structure")
    facts.by_message_length = _aggregate_dimension(pairs, "message_length")

    # Keywords are multi-valued (one campaign can have multiple keywords)
    facts.by_keyword = _aggregate_keywords(pairs)

    logger.info(
        f"Classifications merged: "
        f"{len(facts.by_opening_style)} opening styles, "
        f"{len(facts.by_tone)} tones, "
        f"{len(facts.by_headline_quality)} headline qualities, "
        f"{len(facts.by_cta_strength)} CTA strengths, "
        f"{len(facts.by_emoji_bucket)} emoji buckets, "
        f"{len(facts.by_keyword)} keywords, "
        f"{len(facts.by_message_structure)} message structures, "
        f"{len(facts.by_message_length)} message lengths"
    )

    return facts


def _aggregate_dimension(
    pairs: list[tuple[CanonicalCampaign, CampaignClassification]],
    dimension: str,
) -> list[ClassificationMetrics]:
    """
    Compute aggregated metrics for one classification dimension.

    Groups campaigns by their label for the given dimension,
    then computes CTR, CTOR, and conversion totals for each group.

    Returns sorted by CTR descending (best-performing label first).
    """

    # Group: label → list of campaigns
    groups: dict[str, list[CanonicalCampaign]] = defaultdict(list)
    for campaign, classification in pairs:
        label = getattr(classification, dimension, "unknown")
        groups[label].append(campaign)

    # Compute metrics per label
    results = []
    for label, campaigns in groups.items():
        total_sent = sum(c.sent for c in campaigns)
        total_viewed = sum(c.viewed for c in campaigns)
        total_clicked = sum(c.clicked for c in campaigns)
        total_influenced = sum(c.influenced_conversions for c in campaigns)

        results.append(
            ClassificationMetrics(
                label=label,
                campaign_count=len(campaigns),
                ctr=_rate(total_clicked, total_sent),
                ctor=_rate(total_clicked, total_viewed),
                total_influenced_conversions=total_influenced,
            )
        )

    # Sort by CTR descending
    results.sort(key=lambda x: x.ctr, reverse=True)
    return results


def _aggregate_keywords(
    pairs: list[tuple[CanonicalCampaign, CampaignClassification]],
) -> list[KeywordMetrics]:
    """
    Compute aggregated metrics by keyword.

    Unlike single-label dimensions, each campaign can have multiple keywords.
    A campaign contributes its metrics to EACH keyword it has.

    Returns sorted by campaign_count descending (most common keywords first),
    filtered to keywords that appear in at least 2 campaigns.
    """

    # Group: keyword → list of campaigns
    groups: dict[str, list[CanonicalCampaign]] = defaultdict(list)
    for campaign, classification in pairs:
        for keyword in classification.keywords:
            if keyword:  # skip empty strings
                groups[keyword].append(campaign)

    # Compute metrics per keyword
    results = []
    for keyword, campaigns in groups.items():
        # Only include keywords that appear in 2+ campaigns for meaningful comparison
        if len(campaigns) < 2:
            continue

        total_sent = sum(c.sent for c in campaigns)
        total_viewed = sum(c.viewed for c in campaigns)
        total_clicked = sum(c.clicked for c in campaigns)
        total_influenced = sum(c.influenced_conversions for c in campaigns)

        results.append(
            KeywordMetrics(
                keyword=keyword,
                campaign_count=len(campaigns),
                total_sent=total_sent,
                total_clicked=total_clicked,
                total_influenced_conversions=total_influenced,
                ctr=_rate(total_clicked, total_sent),
                ctor=_rate(total_clicked, total_viewed),
            )
        )

    # Sort by campaign count descending, then CTR
    results.sort(key=lambda x: (-x.campaign_count, -x.ctr))
    return results[:20]  # Top 20 keywords max
