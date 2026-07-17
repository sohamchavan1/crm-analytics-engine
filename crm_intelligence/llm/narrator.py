"""
L2 Narrator — generates structured narrative sections from computed Facts.

This is LLM Call #2 of exactly 2 in the entire pipeline.
Temperature: 0.3 (slightly creative for readable prose, but grounded in facts).

The narrator NEVER invents numbers. It receives pre-computed Facts and
Business/Vertical Profile context. Its job is to:
1. Synthesize findings into executive-readable narrative
2. Provide business-specific (not generic) insights
3. Generate actionable recommendations tied to the company's context
4. Highlight patterns and tell the story behind the numbers

Output is structured JSON with distinct sections that map to report pages.
"""

import json
import logging
from typing import Optional

from crm_intelligence.config import LLM_NARRATE_TEMPERATURE
from crm_intelligence.llm.client import BedrockClientError, call_claude_json
from crm_intelligence.models.facts import Facts
from crm_intelligence.models.profile import BusinessProfile, VerticalProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Narration output structure
# ---------------------------------------------------------------------------


class NarratedInsights:
    """Structured narrative output from L2 call."""

    def __init__(
        self,
        executive_summary: str,
        channel_insights: list[dict],
        offer_insights: list[dict],
        creative_insights: dict,
        timing_insights: dict,
        keyword_insights: dict | None = None,
        emoji_insights: dict | None = None,
        message_structure_insights: dict | None = None,
        label_insights: list[dict] | None = None,
        top_performer_analysis: str = "",
        bottom_performer_analysis: str = "",
        recommendations: list[dict] | None = None,
        trend_commentary: Optional[str] = None,
        # Legacy field kept for backward compat
        segment_insights: list[dict] | None = None,
    ):
        self.executive_summary = executive_summary
        self.channel_insights = channel_insights
        self.offer_insights = offer_insights
        self.creative_insights = creative_insights
        self.timing_insights = timing_insights
        self.keyword_insights = keyword_insights or {}
        self.emoji_insights = emoji_insights or {}
        self.message_structure_insights = message_structure_insights or {}
        self.label_insights = label_insights if label_insights is not None else []
        self.top_performer_analysis = top_performer_analysis
        self.bottom_performer_analysis = bottom_performer_analysis
        self.recommendations = recommendations or []
        self.trend_commentary = trend_commentary
        self.segment_insights = segment_insights or []


# ---------------------------------------------------------------------------
# System prompt for narration
# ---------------------------------------------------------------------------

NARRATE_SYSTEM_PROMPT = """You are a senior CRM Intelligence analyst writing for marketing executives. You produce sharp, business-specific narrative insights from pre-computed campaign analytics.

CRITICAL RULES:
1. NEVER invent, estimate, or compute numbers. Every statistic you mention MUST come from the Facts data provided.
2. NEVER use generic advice like "test and iterate" or "A/B test more". Be SPECIFIC to this business.
3. Reference the company name, vertical, and business context in your narrative.
4. Write in confident, assertive executive voice. No hedging ("might", "could potentially").
5. Each insight must connect a DATA POINT to a BUSINESS IMPLICATION.
6. Recommendations must be concrete actions, not vague suggestions.

You will receive:
- **Facts**: Pre-computed metrics (overall, by channel, by offer, by day/hour, top/bottom performers, creative classifications, keywords, emoji usage, and message structure)
- **Business Profile**: Company context, objectives, constraints
- **Vertical Profile**: The specific business vertical being analyzed

Return ONLY valid JSON with this exact structure:
{
  "executive_summary": "2-3 paragraph summary hitting: dataset scope, key finding, biggest opportunity, critical concern",
  "channel_insights": [
    {"channel": "...", "narrative": "2-3 sentences about this channel's performance with specific numbers", "verdict": "strong|adequate|underperforming"}
  ],
  "offer_insights": [
    {"offer": "...", "narrative": "What this offer type achieved and why", "verdict": "strong|adequate|underperforming"}
  ],
  "creative_insights": {
    "opening_style_narrative": "Which opening styles work best and why (reference the numbers)",
    "tone_narrative": "Which tones drive engagement for this brand",
    "cta_narrative": "CTA effectiveness patterns",
    "overall_creative_verdict": "One line: the creative DNA of top performers vs. bottom"
  },
  "timing_insights": {
    "best_days": "Which days perform best with CTR numbers",
    "best_hours": "Which time slots work and the business reason why",
    "timing_recommendation": "When to send for maximum impact"
  },
  "keyword_insights": {
    "top_keywords_narrative": "Which keyword themes drive the highest CTR/engagement — reference specific keywords and their numbers",
    "underperforming_keywords": "Which themes correlate with lower engagement",
    "keyword_recommendation": "Which themes/topics to lean into and which to rethink"
  },
  "emoji_insights": {
    "emoji_usage_narrative": "How different levels of emoji usage correlate with engagement metrics",
    "optimal_emoji_level": "Which emoji bucket (heavy/moderate/minimal/none) performs best for this brand",
    "emoji_recommendation": "Specific guidance on emoji usage based on the data"
  },
  "message_structure_insights": {
    "structure_narrative": "Which message arrangements (header+body+CTA, single block, etc.) drive the highest engagement",
    "length_narrative": "How message length correlates with CTR/conversions — short vs medium vs long",
    "structure_recommendation": "The ideal message blueprint (structure + length) for this brand based on the data"
  },
  "top_performer_analysis": "What the top 5 campaigns have in common — the formula that works",
  "bottom_performer_analysis": "Why the bottom 5 failed — specific fixable patterns",
  "recommendations": [
    {"priority": 1, "action": "Specific, concrete recommendation", "expected_impact": "What improvement to expect", "rationale": "Data point that supports this"}
  ],
  "trend_commentary": "If comparison data exists, what changed and why. null if no comparison."
}

Remember: You are writing for an executive who has 3 minutes. Every sentence must earn its place."""


# ---------------------------------------------------------------------------
# Main narration function
# ---------------------------------------------------------------------------


def narrate_facts(
    facts: Facts,
    business_profile: BusinessProfile,
    vertical_profile: Optional[VerticalProfile] = None,
    selected_sections: Optional[list[str]] = None,
) -> NarratedInsights:
    """
    Generate structured narrative insights from computed Facts (L2 call).

    This is the second and final LLM call in the pipeline. It receives
    the complete Facts object plus business context, and produces
    human-readable narrative sections for the DOCX report.

    Args:
        facts: Complete computed Facts object (from analytics engine).
        business_profile: Company context and objectives.
        vertical_profile: Optional vertical-specific context.

    Returns:
        NarratedInsights with all narrative sections populated.

    Raises:
        BedrockClientError: If LLM call fails after retries.
    """
    logger.info(
        f"Narrating facts for {facts.meta.company} / {facts.meta.vertical} "
        f"({facts.meta.campaign_count} campaigns)"
    )

    # Build dynamic system prompt based on selected sections
    if selected_sections:
        system_prompt = _build_dynamic_narrate_prompt(selected_sections)
    else:
        system_prompt = NARRATE_SYSTEM_PROMPT

    # Build the user message with all context
    user_message = _build_narration_prompt(facts, business_profile, vertical_profile, selected_sections)

    try:
        response = call_claude_json(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=LLM_NARRATE_TEMPERATURE,
            max_tokens=8192,  # Narration needs more room
        )

        return _parse_narration_response(response)

    except (BedrockClientError, ValueError) as e:
        logger.error(f"Narration failed: {e}")
        # Return minimal fallback so the report can still generate
        return _fallback_narration(facts)


def _build_narration_prompt(
    facts: Facts,
    business_profile: BusinessProfile,
    vertical_profile: Optional[VerticalProfile],
    selected_sections: Optional[list[str]] = None,
) -> str:
    """Assemble the complete context for the narration LLM call."""

    sections = []

    # Business context
    sections.append("## BUSINESS CONTEXT")
    sections.append(f"Company: {business_profile.company_name}")
    sections.append(f"Industry: {business_profile.industry}")
    if business_profile.description:
        sections.append(f"Description: {business_profile.description}")
    if business_profile.brand_positioning:
        sections.append(f"Brand Positioning: {business_profile.brand_positioning}")
    if business_profile.target_audience:
        sections.append(f"Target Audience: {business_profile.target_audience}")
    if business_profile.communication_goals:
        sections.append(f"Communication Goals: {business_profile.communication_goals}")
    if business_profile.retention_strategy:
        sections.append(f"Retention Strategy: {business_profile.retention_strategy}")
    if business_profile.brand_voice:
        sections.append(f"Brand Voice: {business_profile.brand_voice}")
    if business_profile.kpis:
        sections.append(f"KPIs: {', '.join(business_profile.kpis)}")

    # Vertical context
    if vertical_profile:
        sections.append("\n## VERTICAL CONTEXT")
        sections.append(f"Vertical: {vertical_profile.name}")
        if vertical_profile.business_objective:
            sections.append(f"Objective: {vertical_profile.business_objective}")
        if vertical_profile.primary_kpi:
            sections.append(f"Primary KPI: {vertical_profile.primary_kpi}")
        if vertical_profile.typical_cta:
            sections.append(f"Typical CTA: {vertical_profile.typical_cta}")
        if vertical_profile.target_audience:
            sections.append(f"Target Audience: {vertical_profile.target_audience}")

    # Observations (business-specific knowledge)
    if business_profile.observations:
        sections.append("\n## BUSINESS OBSERVATIONS (learned from prior analysis)")
        for obs in business_profile.observations[-10:]:  # Last 10 observations
            sections.append(f"- [{obs.category}] {obs.content}")

    # Facts data (the numbers)
    sections.append("\n## COMPUTED FACTS")
    sections.append(f"Analysis Period: {facts.meta.date_range_start} to {facts.meta.date_range_end}")
    sections.append(f"Total Campaigns: {facts.meta.campaign_count}")
    sections.append(f"Channels: {', '.join(facts.meta.channels)}")

    # Determine which data to include
    secs = set(selected_sections) if selected_sections else None

    # Overall metrics (always included — needed for exec summary)
    sections.append("\n### Overall Metrics")
    sections.append(json.dumps(facts.overall.model_dump(), indent=2))

    # By channel (only if section selected)
    if (secs is None or "channel_performance" in secs) and facts.by_channel:
        sections.append("\n### By Channel")
        sections.append(json.dumps([ch.model_dump() for ch in facts.by_channel], indent=2))

    # By offer (only if section selected)
    if (secs is None or "offer_analysis" in secs) and facts.by_offer:
        sections.append("\n### By Offer Type")
        sections.append(json.dumps([o.model_dump() for o in facts.by_offer], indent=2))

    # By label (only if section selected)
    if (secs is None or "label_analysis" in secs) and facts.by_label:
        sections.append("\n### By Label/Category")
        sections.append(json.dumps([lb.model_dump() for lb in facts.by_label], indent=2))

    # By day
    sections.append("\n### By Day of Week")
    sections.append(json.dumps([d.model_dump() for d in facts.by_day], indent=2))

    # By hour
    sections.append("\n### By Hour Bucket")
    sections.append(json.dumps([h.model_dump() for h in facts.by_hour], indent=2))

    # Creative classifications (if populated)
    if facts.by_opening_style:
        sections.append("\n### By Opening Style (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_opening_style], indent=2))
    if facts.by_tone:
        sections.append("\n### By Tone (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_tone], indent=2))
    if facts.by_cta_strength:
        sections.append("\n### By CTA Strength (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_cta_strength], indent=2))
    if facts.by_emoji_bucket:
        sections.append("\n### By Emoji Usage (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_emoji_bucket], indent=2))
    if facts.by_keyword:
        sections.append("\n### By Keyword Theme (LLM-extracted)")
        sections.append(json.dumps([k.model_dump() for k in facts.by_keyword], indent=2))
    if facts.by_message_structure:
        sections.append("\n### By Message Structure (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_message_structure], indent=2))
    if facts.by_message_length:
        sections.append("\n### By Message Length (LLM-classified)")
        sections.append(json.dumps([c.model_dump() for c in facts.by_message_length], indent=2))

    # Top/bottom performers
    sections.append("\n### Top Performers")
    for i, tp in enumerate(facts.top_performers, 1):
        sections.append(
            f"  #{i}: {tp.campaign_name} | {tp.channel} | {tp.offer} | "
            f"CTR={tp.ctr}% | CTOR={tp.ctor}% | Conv={tp.influenced_conversions}"
        )
        sections.append(f"      Message: {tp.message[:200]}")

    sections.append("\n### Bottom Performers")
    for i, bp in enumerate(facts.bottom_performers, 1):
        sections.append(
            f"  #{i}: {bp.campaign_name} | {bp.channel} | {bp.offer} | "
            f"CTR={bp.ctr}% | CTOR={bp.ctor}% | Conv={bp.influenced_conversions}"
        )
        sections.append(f"      Message: {bp.message[:200]}")

    # Comparison
    if facts.comparison:
        sections.append("\n### Historical Comparison")
        sections.append(json.dumps(facts.comparison.model_dump(), indent=2))

    return "\n".join(sections)


def _build_dynamic_narrate_prompt(selected_sections: list[str]) -> str:
    """
    Build a narrator system prompt requesting only the sections the user selected.

    This reduces token usage and keeps the LLM focused on what matters.
    """
    secs = set(selected_sections)

    # Section-specific JSON schema pieces
    schema_pieces = {}

    if "channel_performance" in secs:
        schema_pieces["channel_insights"] = '''  "channel_insights": [
    {"channel": "...", "narrative": "2-3 sentences about this channel's performance with specific numbers", "verdict": "strong|adequate|underperforming"}
  ]'''

    if "offer_analysis" in secs:
        schema_pieces["offer_insights"] = '''  "offer_insights": [
    {"offer": "...", "narrative": "What this offer type achieved and why", "verdict": "strong|adequate|underperforming"}
  ]'''

    if "label_analysis" in secs:
        schema_pieces["label_insights"] = '''  "label_insights": [
    {"label": "...", "narrative": "How this category performs and why", "verdict": "strong|adequate|underperforming"}
  ]'''

    if "creative_intelligence" in secs:
        schema_pieces["creative_insights"] = '''  "creative_insights": {
    "opening_style_narrative": "Which opening styles work best and why (reference the numbers)",
    "tone_narrative": "Which tones drive engagement for this brand",
    "cta_narrative": "CTA effectiveness patterns",
    "overall_creative_verdict": "One line: the creative DNA of top performers vs. bottom"
  }'''

    if "timing" in secs:
        schema_pieces["timing_insights"] = '''  "timing_insights": {
    "best_days": "Which days perform best with CTR numbers",
    "best_hours": "Which time slots work and the business reason why",
    "timing_recommendation": "When to send for maximum impact"
  }'''

    if "keywords" in secs:
        schema_pieces["keyword_insights"] = '''  "keyword_insights": {
    "top_keywords_narrative": "Which keyword themes drive the highest CTR/engagement",
    "underperforming_keywords": "Which themes correlate with lower engagement",
    "keyword_recommendation": "Which themes/topics to lean into and which to rethink"
  }'''

    if "emoji" in secs:
        schema_pieces["emoji_insights"] = '''  "emoji_insights": {
    "emoji_usage_narrative": "How different levels of emoji usage correlate with engagement metrics",
    "optimal_emoji_level": "Which emoji bucket performs best for this brand",
    "emoji_recommendation": "Specific guidance on emoji usage based on the data"
  }'''

    if "message_structure" in secs:
        schema_pieces["message_structure_insights"] = '''  "message_structure_insights": {
    "structure_narrative": "Which message arrangements drive the highest engagement",
    "length_narrative": "How message length correlates with CTR/conversions",
    "structure_recommendation": "The ideal message blueprint for this brand"
  }'''

    if "performers" in secs:
        schema_pieces["top_performer_analysis"] = '''  "top_performer_analysis": "What the top campaigns have in common — the formula that works"'''
        schema_pieces["bottom_performer_analysis"] = '''  "bottom_performer_analysis": "Why the bottom campaigns failed — specific fixable patterns"'''

    if "recommendations" in secs:
        schema_pieces["recommendations"] = '''  "recommendations": [
    {"priority": 1, "action": "Specific, concrete recommendation", "expected_impact": "What improvement to expect", "rationale": "Data point that supports this"}
  ]'''

    # Always include executive summary
    schema_pieces["executive_summary"] = '''  "executive_summary": "2-3 paragraph summary hitting: dataset scope, key finding, biggest opportunity, critical concern"'''
    schema_pieces["trend_commentary"] = '''  "trend_commentary": "If comparison data exists, what changed and why. null if no comparison."'''

    # Assemble
    schema_lines = ",\n".join(schema_pieces.values())

    prompt = f"""You are a senior CRM Intelligence analyst writing for marketing executives. You produce sharp, business-specific narrative insights from pre-computed campaign analytics.

CRITICAL RULES:
1. NEVER invent, estimate, or compute numbers. Every statistic you mention MUST come from the Facts data provided.
2. NEVER use generic advice like "test and iterate" or "A/B test more". Be SPECIFIC to this business.
3. Reference the company name, vertical, and business context in your narrative.
4. Write in confident, assertive executive voice. No hedging ("might", "could potentially").
5. Each insight must connect a DATA POINT to a BUSINESS IMPLICATION.
6. Recommendations must be concrete actions, not vague suggestions.

You will receive:
- **Facts**: Pre-computed metrics for the selected analysis dimensions
- **Business Profile**: Company context, objectives, constraints
- **Vertical Profile**: The specific business vertical being analyzed

Return ONLY valid JSON with this structure:
{{
{schema_lines}
}}

Remember: You are writing for an executive who has 3 minutes. Every sentence must earn its place."""

    return prompt


def _parse_narration_response(response: dict) -> NarratedInsights:
    """Parse the narration JSON response into NarratedInsights."""

    return NarratedInsights(
        executive_summary=response.get("executive_summary", "Analysis complete."),
        channel_insights=response.get("channel_insights", []),
        offer_insights=response.get("offer_insights", []),
        creative_insights=response.get("creative_insights", {}),
        timing_insights=response.get("timing_insights", {}),
        keyword_insights=response.get("keyword_insights", {}),
        emoji_insights=response.get("emoji_insights", {}),
        message_structure_insights=response.get("message_structure_insights", {}),
        label_insights=response.get("label_insights", []),
        top_performer_analysis=response.get("top_performer_analysis", ""),
        bottom_performer_analysis=response.get("bottom_performer_analysis", ""),
        recommendations=response.get("recommendations", []),
        trend_commentary=response.get("trend_commentary"),
    )


def _fallback_narration(facts: Facts) -> NarratedInsights:
    """Minimal narration when LLM call fails — uses raw facts as prose."""

    summary = (
        f"Analysis of {facts.meta.campaign_count} campaigns across "
        f"{', '.join(facts.meta.channels)} from {facts.meta.date_range_start} "
        f"to {facts.meta.date_range_end}. "
        f"Overall CTR: {facts.overall.overall_ctr}%, "
        f"CTOR: {facts.overall.overall_ctor}%, "
        f"Influenced Conversions: {facts.overall.total_influenced_conversions}."
    )

    return NarratedInsights(
        executive_summary=summary,
        channel_insights=[
            {"channel": ch.channel, "narrative": f"CTR: {ch.ctr}%, CTOR: {ch.ctor}%", "verdict": "adequate"}
            for ch in facts.by_channel
        ],
        offer_insights=[
            {"offer": o.offer, "narrative": f"CTR: {o.ctr}%, CVR: {o.cvr_influenced}%", "verdict": "adequate"}
            for o in facts.by_offer
        ],
        creative_insights={
            "opening_style_narrative": "Classification data available in facts.",
            "tone_narrative": "Classification data available in facts.",
            "cta_narrative": "Classification data available in facts.",
            "overall_creative_verdict": "LLM narration unavailable — see raw metrics.",
        },
        timing_insights={
            "best_days": "See by_day metrics in facts.",
            "best_hours": "See by_hour metrics in facts.",
            "timing_recommendation": "Review timing metrics for optimization.",
        },
        keyword_insights={
            "top_keywords_narrative": "Keyword data available in facts.",
            "underperforming_keywords": "See by_keyword metrics in facts.",
            "keyword_recommendation": "Review keyword themes for optimization.",
        },
        emoji_insights={
            "emoji_usage_narrative": "Emoji data available in facts.",
            "optimal_emoji_level": "See by_emoji_bucket metrics in facts.",
            "emoji_recommendation": "Review emoji usage patterns.",
        },
        message_structure_insights={
            "structure_narrative": "Message structure data available in facts.",
            "length_narrative": "See by_message_length metrics in facts.",
            "structure_recommendation": "Review message arrangement patterns.",
        },
        top_performer_analysis="See top_performers in facts for details.",
        bottom_performer_analysis="See bottom_performers in facts for details.",
        recommendations=[
            {"priority": 1, "action": "Review full facts.json for detailed metrics",
             "expected_impact": "Data-driven decisions", "rationale": "LLM narration unavailable"}
        ],
        trend_commentary=None,
    )
