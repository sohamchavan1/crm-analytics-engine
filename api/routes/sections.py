"""
Sections registry endpoint.

Serves available report sections and their requirements.
Used by the frontend to render the section picker.
"""

from fastapi import APIRouter

from crm_intelligence.sections import SECTION_REGISTRY, get_available_sections

router = APIRouter()


@router.get("")
async def list_sections():
    """
    List all available report sections with metadata.

    Returns section definitions including data requirements,
    L1 dependencies, and default verticals.
    """
    sections = []
    for section in SECTION_REGISTRY.values():
        sections.append({
            "id": section.id,
            "name": section.name,
            "description": section.description,
            "requires_l1": section.requires_l1,
            "l1_dimensions": section.l1_dimensions,
            "requires_data": section.requires_data,
            "default_verticals": section.default_verticals,
        })
    return {"sections": sections}


@router.post("/available")
async def get_available(capabilities: list[str]):
    """
    Given data capabilities (from file scan), return which sections are available.

    Body: list of capability strings, e.g., ["messages", "labels", "multiple_channels"]
    """
    available = get_available_sections(set(capabilities))
    return {
        "available": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "requires_data": s.requires_data,
            }
            for s in available
        ]
    }
