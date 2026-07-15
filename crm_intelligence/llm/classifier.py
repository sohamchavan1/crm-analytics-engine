"""
L1 Classifier — classifies campaign messages along creative dimensions.

This is LLM Call #1 of exactly 2 in the entire pipeline.
Temperature: 0.0 (deterministic classification, not creative writing).

Classifies each campaign message along 8 dimensions:
1. Opening Style — how the message begins (greeting, question, urgency, etc.)
2. Tone — emotional register (emotional, transactional, aspirational, etc.)
3. Headline Quality — how compelling the hook is (strong, moderate, weak)
4. CTA Strength — clarity and urgency of call-to-action (strong, moderate, weak, absent)
5. Emoji Bucket — emoji usage pattern (heavy, moderate, minimal, none)
6. Keywords — 2-3 theme keywords extracted from the message
7. Message Structure — arrangement pattern (header_body_cta, body_cta, etc.)
8. Message Length — short/medium/long classification

The output is structured JSON that gets merged back into Facts
for aggregation by classification dimension.
"""

import logging
from typing import Any

from crm_intelligence.config import LLM_CLASSIFY_TEMPERATURE, MAX_CAMPAIGNS_PER_LLM_BATCH
from crm_intelligence.llm.client import BedrockClientError, call_claude_json
from crm_intelligence.models.campaign import CanonicalCampaign

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification taxonomy (fixed labels — LLM must choose from these)
# ---------------------------------------------------------------------------

OPENING_STYLES = [
    "personalized_greeting",  # "Hi [Name]!", "Dear Member"
    "question",  # "Looking for a getaway?", "Ready to explore?"
    "urgency",  # "Last chance!", "Offer ends today"
    "benefit_lead",  # "Get 2 free nights", "Save 40%"
    "emotional",  # "You deserve a break", "Make memories"
    "announcement",  # "Exciting news!", "Introducing..."
    "direct",  # Straight to the point, no hook
]

TONES = [
    "emotional",  # Tugs at feelings, aspirational language
    "transactional",  # Factual, deal-focused, numbers-heavy
    "aspirational",  # Dreams, lifestyle, transformation
    "urgency",  # FOMO, deadlines, scarcity
    "informational",  # Neutral, educational, explaining features
    "playful",  # Fun, casual, light-hearted
]

HEADLINE_QUALITIES = ["strong", "moderate", "weak"]
CTA_STRENGTHS = ["strong", "moderate", "weak", "absent"]
EMOJI_BUCKETS = ["heavy", "moderate", "minimal", "none"]


# ---------------------------------------------------------------------------
# System prompt for classification
# ---------------------------------------------------------------------------

MESSAGE_STRUCTURES = [
    "header_body_cta",       # Clear title/header + body text + CTA button/link
    "body_cta",              # No header, straight into body + CTA
    "greeting_body_cta",     # Personal greeting + body + CTA
    "single_block",          # One continuous block, no clear sections
    "multi_section",         # Multiple distinct sections/paragraphs with breaks
]

MESSAGE_LENGTHS = ["short", "medium", "long"]  # <50 words, 50-100, 100+


CLASSIFY_SYSTEM_PROMPT = """You are a CRM campaign message classifier. Your job is to analyze marketing messages and classify them along 8 creative dimensions.

You will receive a JSON array of campaign objects, each with:
- "id": a unique index (0-based)
- "channel": the communication channel
- "message": the full message text
- "title": optional title/header (may be null)

For EACH campaign, classify it along these dimensions:

1. **opening_style** — How does the message begin? Choose exactly one:
   - "personalized_greeting": Starts with name/member acknowledgment
   - "question": Opens with a question to engage
   - "urgency": Opens with time pressure or scarcity
   - "benefit_lead": Opens with the value proposition/offer
   - "emotional": Opens with emotional language or aspiration
   - "announcement": Opens with news or revelation
   - "direct": No hook, gets straight to information

2. **tone** — What is the overall emotional register? Choose exactly one:
   - "emotional": Appeals to feelings, memories, relationships
   - "transactional": Deal-focused, numbers and savings
   - "aspirational": Lifestyle, dreams, transformation
   - "urgency": Time-limited, FOMO, scarcity-driven
   - "informational": Neutral, factual, feature-focused
   - "playful": Fun, casual, uses humor or lightness

3. **headline_quality** — How compelling is the hook/opening? Choose exactly one:
   - "strong": Immediately engaging, specific benefit, creates curiosity
   - "moderate": Reasonable hook but generic or predictable
   - "weak": No clear hook, buried value proposition, bland

4. **cta_strength** — How clear and compelling is the call-to-action? Choose exactly one:
   - "strong": Clear action verb, specific benefit, urgency element
   - "moderate": Action is clear but generic ("Click here", "Learn more")
   - "weak": CTA is vague or buried in text
   - "absent": No discernible call-to-action

5. **emoji_bucket** — How are emojis used? Choose exactly one:
   - "heavy": 4+ emojis, emoji-driven visual style
   - "moderate": 2-3 emojis, accent use
   - "minimal": 1 emoji, sparse
   - "none": Zero emojis

6. **keywords** — Extract 2-3 primary theme keywords from the message. These should be the core concepts/hooks being used (e.g., "free nights", "anniversary", "luxury", "limited time", "family", "savings", "exclusive", "reward", "upgrade"). Return as a JSON array of lowercase strings.

7. **message_structure** — How is the message arranged? Choose exactly one:
   - "header_body_cta": Clear title/header + body text + CTA button/link
   - "body_cta": No header, straight into body + CTA
   - "greeting_body_cta": Personal greeting + body + CTA
   - "single_block": One continuous block, no clear sections
   - "multi_section": Multiple distinct sections/paragraphs with visual breaks

8. **message_length** — How long is the message? Choose exactly one:
   - "short": Under 50 words, punchy
   - "medium": 50-100 words, balanced
   - "long": Over 100 words, detailed

CRITICAL RULES:
- Return ONLY valid JSON. No markdown, no explanation, no preamble.
- The response must be a JSON array with one object per campaign, in the same order.
- Each object has keys: "id", "opening_style", "tone", "headline_quality", "cta_strength", "emoji_bucket", "keywords", "message_structure", "message_length"
- Use ONLY the exact label strings listed above for classification fields. No variations.
- keywords must be a JSON array of 2-3 lowercase strings.
- If unsure, pick the closest match. Never invent new labels.

Example output format:
[
  {"id": 0, "opening_style": "benefit_lead", "tone": "transactional", "headline_quality": "strong", "cta_strength": "moderate", "emoji_bucket": "moderate", "keywords": ["free nights", "resort", "luxury"], "message_structure": "header_body_cta", "message_length": "medium"},
  {"id": 1, "opening_style": "emotional", "tone": "aspirational", "headline_quality": "moderate", "cta_strength": "strong", "emoji_bucket": "none", "keywords": ["anniversary", "celebration", "memories"], "message_structure": "greeting_body_cta", "message_length": "short"}
]"""


# ---------------------------------------------------------------------------
# Dynamic prompt building
# ---------------------------------------------------------------------------

ALL_DIMENSIONS = [
    "opening_style", "tone", "headline_quality", "cta_strength",
    "emoji_bucket", "keywords", "message_structure", "message_length",
]

# Individual dimension prompt blocks (assembled dynamically)
_DIMENSION_PROMPTS = {
    "opening_style": '''**opening_style** — How does the message begin? Choose exactly one:
   - "personalized_greeting": Starts with name/member acknowledgment
   - "question": Opens with a question to engage
   - "urgency": Opens with time pressure or scarcity
   - "benefit_lead": Opens with the value proposition/offer
   - "emotional": Opens with emotional language or aspiration
   - "announcement": Opens with news or revelation
   - "direct": No hook, gets straight to information''',

    "tone": '''**tone** — What is the overall emotional register? Choose exactly one:
   - "emotional": Appeals to feelings, memories, relationships
   - "transactional": Deal-focused, numbers and savings
   - "aspirational": Lifestyle, dreams, transformation
   - "urgency": Time-limited, FOMO, scarcity-driven
   - "informational": Neutral, factual, feature-focused
   - "playful": Fun, casual, uses humor or lightness''',

    "headline_quality": '''**headline_quality** — How compelling is the hook/opening? Choose exactly one:
   - "strong": Immediately engaging, specific benefit, creates curiosity
   - "moderate": Reasonable hook but generic or predictable
   - "weak": No clear hook, buried value proposition, bland''',

    "cta_strength": '''**cta_strength** — How clear and compelling is the call-to-action? Choose exactly one:
   - "strong": Clear action verb, specific benefit, urgency element
   - "moderate": Action is clear but generic ("Click here", "Learn more")
   - "weak": CTA is vague or buried in text
   - "absent": No discernible call-to-action''',

    "emoji_bucket": '''**emoji_bucket** — How are emojis used? Choose exactly one:
   - "heavy": 4+ emojis, emoji-driven visual style
   - "moderate": 2-3 emojis, accent use
   - "minimal": 1 emoji, sparse
   - "none": Zero emojis''',

    "keywords": '''**keywords** — Extract 2-3 primary theme keywords from the message. These should be the core concepts/hooks being used (e.g., "free nights", "anniversary", "luxury", "limited time", "family", "savings", "exclusive", "reward", "upgrade"). Return as a JSON array of lowercase strings.''',

    "message_structure": '''**message_structure** — How is the message arranged? Choose exactly one:
   - "header_body_cta": Clear title/header + body text + CTA button/link
   - "body_cta": No header, straight into body + CTA
   - "greeting_body_cta": Personal greeting + body + CTA
   - "single_block": One continuous block, no clear sections
   - "multi_section": Multiple distinct sections/paragraphs with visual breaks''',

    "message_length": '''**message_length** — How long is the message? Choose exactly one:
   - "short": Under 50 words, punchy
   - "medium": 50-100 words, balanced
   - "long": Over 100 words, detailed''',
}


def _build_dynamic_prompt(dimensions: list[str]) -> str:
    """
    Build a classification system prompt for only the requested dimensions.

    This keeps the LLM focused and reduces token usage when only a subset
    of dimensions is needed.
    """
    dim_count = len(dimensions)

    # Header
    lines = [
        f"You are a CRM campaign message classifier. Your job is to analyze marketing messages and classify them along {dim_count} creative dimension{'s' if dim_count > 1 else ''}.",
        "",
        "You will receive a JSON array of campaign objects, each with:",
        '- "id": a unique index (0-based)',
        '- "channel": the communication channel',
        '- "message": the full message text',
        '- "title": optional title/header (may be null)',
        "",
        "For EACH campaign, classify it along these dimensions:",
        "",
    ]

    # Add dimension descriptions
    for i, dim in enumerate(dimensions, 1):
        if dim in _DIMENSION_PROMPTS:
            lines.append(f"{i}. {_DIMENSION_PROMPTS[dim]}")
            lines.append("")

    # Build the output keys list
    output_keys = ["id"] + dimensions

    # Rules
    lines.append("CRITICAL RULES:")
    lines.append("- Return ONLY valid JSON. No markdown, no explanation, no preamble.")
    lines.append("- The response must be a JSON array with one object per campaign, in the same order.")
    keys_str = ", ".join(f'"{k}"' for k in output_keys)
    lines.append(f"- Each object has keys: {keys_str}")
    lines.append("- Use ONLY the exact label strings listed above for classification fields. No variations.")
    if "keywords" in dimensions:
        lines.append("- keywords must be a JSON array of 2-3 lowercase strings.")
    lines.append("- If unsure, pick the closest match. Never invent new labels.")

    # Example
    lines.append("")
    lines.append("Example output format:")
    example_obj = {"id": 0}
    for dim in dimensions:
        if dim == "keywords":
            example_obj[dim] = ["theme1", "theme2"]
        elif dim == "opening_style":
            example_obj[dim] = "benefit_lead"
        elif dim == "tone":
            example_obj[dim] = "transactional"
        elif dim == "headline_quality":
            example_obj[dim] = "strong"
        elif dim == "cta_strength":
            example_obj[dim] = "moderate"
        elif dim == "emoji_bucket":
            example_obj[dim] = "moderate"
        elif dim == "message_structure":
            example_obj[dim] = "header_body_cta"
        elif dim == "message_length":
            example_obj[dim] = "medium"

    import json
    lines.append(f"[{json.dumps(example_obj)}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Classification data types
# ---------------------------------------------------------------------------


class CampaignClassification:
    """Classification result for one campaign."""

    def __init__(
        self,
        campaign_index: int,
        opening_style: str,
        tone: str,
        headline_quality: str,
        cta_strength: str,
        emoji_bucket: str,
        keywords: list[str] | None = None,
        message_structure: str = "single_block",
        message_length: str = "medium",
    ):
        self.campaign_index = campaign_index
        self.opening_style = opening_style
        self.tone = tone
        self.headline_quality = headline_quality
        self.cta_strength = cta_strength
        self.emoji_bucket = emoji_bucket
        self.keywords = keywords or []
        self.message_structure = message_structure
        self.message_length = message_length

    def is_valid(self) -> bool:
        """Check all labels are from the allowed taxonomy."""
        return (
            self.opening_style in OPENING_STYLES
            and self.tone in TONES
            and self.headline_quality in HEADLINE_QUALITIES
            and self.cta_strength in CTA_STRENGTHS
            and self.emoji_bucket in EMOJI_BUCKETS
            and self.message_structure in MESSAGE_STRUCTURES
            and self.message_length in MESSAGE_LENGTHS
        )


# ---------------------------------------------------------------------------
# Main classification function
# ---------------------------------------------------------------------------


def classify_campaigns(
    campaigns: list[CanonicalCampaign],
    dimensions: list[str] | None = None,
) -> list[CampaignClassification]:
    """
    Classify all campaigns along creative dimensions using Claude (L1 call).

    This is a single LLM call (or batched if > MAX_CAMPAIGNS_PER_LLM_BATCH).
    Temperature is 0.0 for deterministic classification.

    Args:
        campaigns: List of CanonicalCampaign objects to classify.
        dimensions: Which dimensions to classify. If None, all 8 are used.
            Possible values: opening_style, tone, headline_quality, cta_strength,
            emoji_bucket, keywords, message_structure, message_length.

    Returns:
        List of CampaignClassification objects, one per campaign (same order).
        If LLM fails for some campaigns, those get default "direct/transactional" labels.

    Raises:
        BedrockClientError: If all LLM call attempts fail.
    """
    if not campaigns:
        return []

    # Default: all dimensions
    if dimensions is None:
        dims = ALL_DIMENSIONS
    else:
        dims = [d for d in dimensions if d in ALL_DIMENSIONS]
        if not dims:
            dims = ALL_DIMENSIONS

    # Build dynamic system prompt based on requested dimensions
    system_prompt = _build_dynamic_prompt(dims)

    logger.info(f"Classifying {len(campaigns)} campaigns (L1 call, dimensions: {dims})")

    all_classifications: list[CampaignClassification] = []

    # Process in batches if needed
    for batch_start in range(0, len(campaigns), MAX_CAMPAIGNS_PER_LLM_BATCH):
        batch = campaigns[batch_start : batch_start + MAX_CAMPAIGNS_PER_LLM_BATCH]
        batch_classifications = _classify_batch(batch, batch_start, system_prompt, dims)
        all_classifications.extend(batch_classifications)

    logger.info(f"Classification complete: {len(all_classifications)} campaigns classified")
    return all_classifications


def _classify_batch(
    batch: list[CanonicalCampaign], offset: int,
    system_prompt: str | None = None,
    dimensions: list[str] | None = None,
) -> list[CampaignClassification]:
    """Classify a single batch of campaigns."""

    if system_prompt is None:
        system_prompt = CLASSIFY_SYSTEM_PROMPT

    # Build the input payload
    input_data = []
    for i, c in enumerate(batch):
        input_data.append(
            {
                "id": i,
                "channel": c.channel,
                "message": c.message[:1000],  # Truncate very long messages
                "title": c.title,
            }
        )

    user_message = (
        f"Classify the following {len(input_data)} campaign messages.\n\n"
        f"{_format_json(input_data)}"
    )

    try:
        response = call_claude_json(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=LLM_CLASSIFY_TEMPERATURE,
            max_tokens=4096,
        )

        return _parse_classification_response(response, len(batch), offset)

    except (BedrockClientError, ValueError) as e:
        logger.error(f"Classification batch failed: {e}")
        # Return defaults for this batch rather than crashing the whole pipeline
        return _default_classifications(len(batch), offset)


def _parse_classification_response(
    response: Any, expected_count: int, offset: int
) -> list[CampaignClassification]:
    """Parse and validate the LLM classification response."""

    if not isinstance(response, list):
        logger.warning("LLM response is not a list, using defaults")
        return _default_classifications(expected_count, offset)

    classifications = []

    for i in range(expected_count):
        # Find the entry for this index
        entry = None
        for item in response:
            if isinstance(item, dict) and item.get("id") == i:
                entry = item
                break

        if entry is None:
            # Missing entry — use default
            classifications.append(_default_classification(offset + i))
            continue

        # Extract keywords — must be a list of strings
        raw_keywords = entry.get("keywords", [])
        if not isinstance(raw_keywords, list):
            raw_keywords = []
        keywords = [str(k).lower().strip() for k in raw_keywords if k][:5]

        # Extract and validate labels
        clf = CampaignClassification(
            campaign_index=offset + i,
            opening_style=entry.get("opening_style", "direct"),
            tone=entry.get("tone", "transactional"),
            headline_quality=entry.get("headline_quality", "moderate"),
            cta_strength=entry.get("cta_strength", "moderate"),
            emoji_bucket=entry.get("emoji_bucket", "none"),
            keywords=keywords,
            message_structure=entry.get("message_structure", "single_block"),
            message_length=entry.get("message_length", "medium"),
        )

        # Validate — if any label is off-taxonomy, fix it
        if not clf.is_valid():
            logger.debug(
                f"Campaign {offset + i}: invalid labels detected, "
                f"falling back to defaults for invalid fields"
            )
            if clf.opening_style not in OPENING_STYLES:
                clf.opening_style = "direct"
            if clf.tone not in TONES:
                clf.tone = "transactional"
            if clf.headline_quality not in HEADLINE_QUALITIES:
                clf.headline_quality = "moderate"
            if clf.cta_strength not in CTA_STRENGTHS:
                clf.cta_strength = "moderate"
            if clf.emoji_bucket not in EMOJI_BUCKETS:
                clf.emoji_bucket = "none"
            if clf.message_structure not in MESSAGE_STRUCTURES:
                clf.message_structure = "single_block"
            if clf.message_length not in MESSAGE_LENGTHS:
                clf.message_length = "medium"

        classifications.append(clf)

    return classifications


def _default_classification(index: int) -> CampaignClassification:
    """Return a safe default classification for one campaign."""
    return CampaignClassification(
        campaign_index=index,
        opening_style="direct",
        tone="transactional",
        headline_quality="moderate",
        cta_strength="moderate",
        emoji_bucket="none",
    )


def _default_classifications(count: int, offset: int) -> list[CampaignClassification]:
    """Return default classifications for a batch that failed."""
    return [_default_classification(offset + i) for i in range(count)]


def _format_json(data: Any) -> str:
    """Format data as compact JSON for the LLM prompt."""
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)
