"""
Section Registry — defines all available report sections and their requirements.

This is the CONTROL PLANE of the report generation system.
Each section declares:
- What data it needs (multiple_channels, messages, labels, offer_extraction)
- Whether it needs L1 classification
- Which L1 dimensions it requires (if any)
- Human-readable metadata for the UI

The pipeline reads this registry to:
1. Show available sections based on data scan results
2. Skip unnecessary computation steps
3. Build dynamic LLM prompts for only the selected sections
4. Render only selected sections in the DOCX
"""

from dataclasses import dataclass, field


@dataclass
class SectionDef:
    """Definition of one report section."""

    id: str
    name: str
    description: str
    requires_l1: bool = False
    l1_dimensions: list[str] = field(default_factory=list)
    requires_data: list[str] = field(default_factory=list)
    # Sections requiring L2 narration (almost all do, but performers/timing can
    # work with just facts if L2 is skipped)
    requires_l2: bool = True
    # Default enabled for these verticals (UI pre-checks)
    default_verticals: list[str] = field(default_factory=lambda: ["all"])


# ---------------------------------------------------------------------------
# The Registry
# ---------------------------------------------------------------------------

SECTION_REGISTRY: dict[str, SectionDef] = {}


def _register(section: SectionDef) -> None:
    """Register a section in the global registry."""
    SECTION_REGISTRY[section.id] = section


# --- Always-available sections (no special data requirements) ---

_register(SectionDef(
    id="performers",
    name="Top & Bottom Performers",
    description="Ranked campaigns by performance with analysis of what works and what fails",
    requires_l1=False,
    requires_data=[],  # Just needs campaigns — always available
    default_verticals=["all"],
))

_register(SectionDef(
    id="timing",
    name="Timing Analysis",
    description="Best days and time slots for sending campaigns",
    requires_l1=False,
    requires_data=[],
    default_verticals=["all"],
))

_register(SectionDef(
    id="recommendations",
    name="Recommendations",
    description="Prioritized, actionable recommendations with data support",
    requires_l1=False,
    requires_data=[],
    default_verticals=["all"],
))

# --- Data-dependent sections ---

_register(SectionDef(
    id="channel_performance",
    name="Channel Performance",
    description="Comparative performance across channels (Push, WhatsApp, RCS, Email, etc.)",
    requires_l1=False,
    requires_data=["multiple_channels"],
    default_verticals=["all"],
))

_register(SectionDef(
    id="offer_analysis",
    name="Offer Type Analysis",
    description="Performance breakdown by offer/reward type extracted from campaign names",
    requires_l1=False,
    requires_data=["offer_extraction"],
    default_verticals=["hospitality", "membership", "loyalty"],
))

_register(SectionDef(
    id="label_analysis",
    name="Category/Label Analysis",
    description="Performance by campaign tags/categories (from Labels column)",
    requires_l1=False,
    requires_data=["labels"],
    default_verticals=["ecommerce", "retail", "fashion"],
))

# --- LLM-classified sections (need L1 call) ---

_register(SectionDef(
    id="creative_intelligence",
    name="Creative Intelligence",
    description="Opening style, tone, and CTA strength analysis from message content",
    requires_l1=True,
    l1_dimensions=["opening_style", "tone", "headline_quality", "cta_strength"],
    requires_data=["messages"],
    default_verticals=["all"],
))

_register(SectionDef(
    id="keywords",
    name="Keywords Analysis",
    description="Theme keywords extracted from messages and their performance correlation",
    requires_l1=True,
    l1_dimensions=["keywords"],
    requires_data=["messages"],
    default_verticals=["all"],
))

_register(SectionDef(
    id="emoji",
    name="Emoji Analysis",
    description="Emoji usage patterns and their correlation with engagement metrics",
    requires_l1=True,
    l1_dimensions=["emoji_bucket"],
    requires_data=["messages"],
    default_verticals=["all"],
))

_register(SectionDef(
    id="message_structure",
    name="Headers & Message Arrangement",
    description="Message layout patterns and length correlation with performance",
    requires_l1=True,
    l1_dimensions=["message_structure", "message_length"],
    requires_data=["messages"],
    default_verticals=["all"],
))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_required_l1_dimensions(selected_sections: list[str]) -> list[str]:
    """
    Given selected section IDs, return the L1 classification dimensions needed.

    If empty, L1 call can be skipped entirely.
    """
    dimensions = set()
    for section_id in selected_sections:
        section = SECTION_REGISTRY.get(section_id)
        if section and section.requires_l1:
            dimensions.update(section.l1_dimensions)
    return sorted(dimensions)


def needs_l1(selected_sections: list[str]) -> bool:
    """Check if any selected section requires L1 classification."""
    return len(get_required_l1_dimensions(selected_sections)) > 0


def needs_l2(selected_sections: list[str]) -> bool:
    """Check if any selected section requires L2 narration."""
    for section_id in selected_sections:
        section = SECTION_REGISTRY.get(section_id)
        if section and section.requires_l2:
            return True
    return False


def get_available_sections(data_capabilities: set[str]) -> list[SectionDef]:
    """
    Given data capabilities from a file scan, return sections that are available.

    Args:
        data_capabilities: Set of capability strings detected in the data.
            Possible values: "multiple_channels", "messages", "labels",
            "offer_extraction", "segments"

    Returns:
        List of SectionDef objects that are available given the data.
    """
    available = []
    for section in SECTION_REGISTRY.values():
        # Section is available if ALL its data requirements are met
        if all(req in data_capabilities for req in section.requires_data):
            available.append(section)
    return available


def get_default_sections(vertical: str, data_capabilities: set[str]) -> list[str]:
    """
    Get sensible default section selections for a vertical + data combination.

    Returns section IDs that should be pre-checked in the UI.
    """
    available = get_available_sections(data_capabilities)
    defaults = []

    vertical_lower = vertical.lower()

    for section in available:
        # Include if "all" is in default_verticals or if vertical matches
        if "all" in section.default_verticals:
            defaults.append(section.id)
        elif any(v in vertical_lower for v in section.default_verticals):
            defaults.append(section.id)

    return defaults


# ---------------------------------------------------------------------------
# All section IDs (for validation)
# ---------------------------------------------------------------------------

ALL_SECTION_IDS = list(SECTION_REGISTRY.keys())
