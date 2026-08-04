"""
Report comparison endpoint.

Accepts two run_ids from the same brand, loads their facts + insights,
calls Claude to generate a structured comparison narrative, and caches the result.

Also provides:
- GET /api/compare — list all past comparisons
- GET /api/compare/{comparison_id}/download — DOCX export of a comparison

Storage: storage/comparisons/{comparison_id}.json
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from crm_intelligence.llm.client import call_claude_json

logger = logging.getLogger(__name__)
router = APIRouter()

RUNS_DIR = Path("storage/runs")
FACTS_DIR = Path("storage/facts")
INSIGHTS_DIR = Path("storage/insights")
COMPARISONS_DIR = Path("storage/comparisons")
COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)


class CompareRequest(BaseModel):
    run_id_a: str
    run_id_b: str


def _load_run(run_id: str) -> dict:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Report not found: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_facts(run_id: str) -> Optional[dict]:
    path = FACTS_DIR / f"{run_id}_facts.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_insights(run_id: str) -> Optional[dict]:
    path = INSIGHTS_DIR / f"{run_id}_insights.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _comparison_id(run_id_a: str, run_id_b: str) -> str:
    """Deterministic ID for a comparison pair (order-independent)."""
    pair = sorted([run_id_a, run_id_b])
    return hashlib.md5(f"{pair[0]}:{pair[1]}".encode()).hexdigest()[:12]


COMPARISON_SYSTEM_PROMPT = """You are a CRM analytics expert comparing two campaign performance reports for the same brand.

Your job is to produce a structured comparison that highlights:
1. What improved between the periods
2. What declined
3. Key shifts in strategy or performance patterns
4. One actionable recommendation based on the trend

Output ONLY valid JSON with this exact structure:
{
  "summary": "2-3 sentence executive summary of the comparison — what's the headline story?",
  "metrics_delta": {
    "ctr_change": <number: percentage point change>,
    "ctor_change": <number: percentage point change>,
    "conversion_change": <number: absolute change in influenced conversions>,
    "sent_change": <number: absolute change in total sent>,
    "delivery_rate_change": <number: percentage point change>
  },
  "improvements": ["list of 2-4 things that got better"],
  "declines": ["list of 1-3 things that got worse, or empty if none"],
  "strategy_shifts": ["list of 1-3 notable changes in approach — channel mix, tone, timing, etc."],
  "recommendation": "One concrete, actionable recommendation based on the comparison trends",
  "context_note": "Brief note on comparability — campaign volume differences, time period context, etc. Null if straightforward comparison."
}

Be specific with numbers. Reference actual metrics. Do not hedge excessively — deliver clear findings."""


def _build_comparison_prompt(
    run_a: dict, facts_a: dict, insights_a: Optional[dict],
    run_b: dict, facts_b: dict, insights_b: Optional[dict],
) -> str:
    """Build the user message for the comparison LLM call."""
    parts = []

    parts.append("=== REPORT A (OLDER) ===")
    parts.append(f"Company: {run_a.get('company')}")
    parts.append(f"Vertical: {run_a.get('vertical_code')}")
    parts.append(f"Period: {run_a.get('date_range_start')} to {run_a.get('date_range_end')}")
    parts.append(f"Campaigns: {run_a.get('campaign_count')}")
    parts.append(f"Channels: {', '.join(run_a.get('channels', []))}")
    parts.append(f"\nOverall Metrics A: {json.dumps(facts_a.get('overall', {}), indent=2)}")

    if facts_a.get("by_channel"):
        parts.append(f"Channel Breakdown A: {json.dumps(facts_a['by_channel'], indent=2)}")
    if facts_a.get("by_day"):
        parts.append(f"Day Performance A: {json.dumps(facts_a['by_day'], indent=2)}")
    if facts_a.get("top_performers"):
        top_a = [{"name": p["campaign_name"], "ctr": p["ctr"], "ctor": p["ctor"]} for p in facts_a["top_performers"][:3]]
        parts.append(f"Top 3 Performers A: {json.dumps(top_a)}")
    if insights_a and insights_a.get("executive_summary"):
        parts.append(f"Executive Summary A: {insights_a['executive_summary'][:500]}")

    parts.append("\n\n=== REPORT B (NEWER) ===")
    parts.append(f"Company: {run_b.get('company')}")
    parts.append(f"Vertical: {run_b.get('vertical_code')}")
    parts.append(f"Period: {run_b.get('date_range_start')} to {run_b.get('date_range_end')}")
    parts.append(f"Campaigns: {run_b.get('campaign_count')}")
    parts.append(f"Channels: {', '.join(run_b.get('channels', []))}")
    parts.append(f"\nOverall Metrics B: {json.dumps(facts_b.get('overall', {}), indent=2)}")

    if facts_b.get("by_channel"):
        parts.append(f"Channel Breakdown B: {json.dumps(facts_b['by_channel'], indent=2)}")
    if facts_b.get("by_day"):
        parts.append(f"Day Performance B: {json.dumps(facts_b['by_day'], indent=2)}")
    if facts_b.get("top_performers"):
        top_b = [{"name": p["campaign_name"], "ctr": p["ctr"], "ctor": p["ctor"]} for p in facts_b["top_performers"][:3]]
        parts.append(f"Top 3 Performers B: {json.dumps(top_b)}")
    if insights_b and insights_b.get("executive_summary"):
        parts.append(f"Executive Summary B: {insights_b['executive_summary'][:500]}")

    parts.append("\n\nCompare Report A (older) to Report B (newer). Focus on what changed and why it matters.")

    return "\n".join(parts)


@router.post("")
async def compare_reports(req: CompareRequest):
    """
    Compare two reports. Returns cached result if available, otherwise runs LLM comparison.

    Both reports must belong to the same brand. Returns structured comparison with
    delta metrics, improvements, declines, and an actionable recommendation.
    """
    # Load both runs
    run_a = _load_run(req.run_id_a)
    run_b = _load_run(req.run_id_b)

    # Validate same brand
    if run_a.get("company", "").lower() != run_b.get("company", "").lower():
        raise HTTPException(
            400,
            "Cannot compare reports from different brands. Select two reports from the same brand."
        )

    # Check for cached comparison
    comp_id = _comparison_id(req.run_id_a, req.run_id_b)
    cache_path = COMPARISONS_DIR / f"{comp_id}.json"

    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached

    # Load facts (required)
    facts_a = _load_facts(req.run_id_a)
    facts_b = _load_facts(req.run_id_b)

    if not facts_a or not facts_b:
        raise HTTPException(400, "Both reports must have computed facts to compare.")

    # Load insights (optional)
    insights_a = _load_insights(req.run_id_a)
    insights_b = _load_insights(req.run_id_b)

    # Determine order: A should be the earlier period (by data date, not generation date)
    # User may generate Jan report after March report — use date_range_start
    period_a = run_a.get("date_range_start") or run_a.get("created_at", "")
    period_b = run_b.get("date_range_start") or run_b.get("created_at", "")
    if period_a > period_b:
        # Swap so A covers the earlier period
        run_a, run_b = run_b, run_a
        facts_a, facts_b = facts_b, facts_a
        insights_a, insights_b = insights_b, insights_a

    # Build prompt and call LLM
    user_message = _build_comparison_prompt(run_a, facts_a, insights_a, run_b, facts_b, insights_b)

    try:
        comparison = call_claude_json(
            system_prompt=COMPARISON_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.3,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(f"Comparison LLM call failed: {e}")
        raise HTTPException(500, f"AI comparison failed: {str(e)}")

    # Build full response with metadata
    result = {
        "comparison_id": comp_id,
        "run_a": {
            "run_id": run_a.get("run_id"),
            "company": run_a.get("company"),
            "vertical_code": run_a.get("vertical_code"),
            "date_range_start": run_a.get("date_range_start"),
            "date_range_end": run_a.get("date_range_end"),
            "campaign_count": run_a.get("campaign_count"),
            "channels": run_a.get("channels", []),
            "overall": facts_a.get("overall", {}),
        },
        "run_b": {
            "run_id": run_b.get("run_id"),
            "company": run_b.get("company"),
            "vertical_code": run_b.get("vertical_code"),
            "date_range_start": run_b.get("date_range_start"),
            "date_range_end": run_b.get("date_range_end"),
            "campaign_count": run_b.get("campaign_count"),
            "channels": run_b.get("channels", []),
            "overall": facts_b.get("overall", {}),
        },
        "comparison": comparison,
    }

    # Cache result
    cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Comparison {comp_id} cached successfully")

    return result


@router.get("")
async def list_comparisons(limit: int = Query(50, ge=1, le=200)):
    """List all past comparisons, most recent first."""
    if not COMPARISONS_DIR.exists():
        return {"comparisons": [], "total": 0}

    comparisons = []
    for f in sorted(COMPARISONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            comparisons.append({
                "comparison_id": data.get("comparison_id"),
                "company": data.get("run_a", {}).get("company"),
                "vertical_code": data.get("run_a", {}).get("vertical_code"),
                "run_a_period": f"{data.get('run_a', {}).get('date_range_start', '?')} — {data.get('run_a', {}).get('date_range_end', '?')}",
                "run_b_period": f"{data.get('run_b', {}).get('date_range_start', '?')} — {data.get('run_b', {}).get('date_range_end', '?')}",
                "run_a_id": data.get("run_a", {}).get("run_id"),
                "run_b_id": data.get("run_b", {}).get("run_id"),
                "summary": data.get("comparison", {}).get("summary", ""),
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
            if len(comparisons) >= limit:
                break
        except Exception:
            continue

    return {"comparisons": comparisons, "total": len(comparisons)}


@router.get("/{comparison_id}")
async def get_comparison(comparison_id: str):
    """Get a specific comparison by ID."""
    cache_path = COMPARISONS_DIR / f"{comparison_id}.json"
    if not cache_path.exists():
        raise HTTPException(404, f"Comparison not found: {comparison_id}")
    return json.loads(cache_path.read_text(encoding="utf-8"))


@router.delete("/{comparison_id}")
async def delete_comparison(comparison_id: str):
    """Delete a comparison."""
    cache_path = COMPARISONS_DIR / f"{comparison_id}.json"
    if not cache_path.exists():
        raise HTTPException(404, f"Comparison not found: {comparison_id}")
    cache_path.unlink()
    # Also delete DOCX if it exists
    docx_path = COMPARISONS_DIR / f"{comparison_id}.docx"
    docx_path.unlink(missing_ok=True)
    return {"status": "deleted", "comparison_id": comparison_id}


@router.get("/{comparison_id}/download")
async def download_comparison(comparison_id: str):
    """Download comparison as a DOCX report."""
    cache_path = COMPARISONS_DIR / f"{comparison_id}.json"
    if not cache_path.exists():
        raise HTTPException(404, f"Comparison not found: {comparison_id}")

    docx_path = COMPARISONS_DIR / f"{comparison_id}.docx"

    # Generate DOCX if not already cached
    if not docx_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        _render_comparison_docx(data, docx_path)

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"Comparison_{comparison_id}.docx",
    )


# ---------------------------------------------------------------------------
# DOCX Renderer for Comparisons
# ---------------------------------------------------------------------------


def _render_comparison_docx(data: dict, output_path: Path) -> None:
    """Render a comparison result as a professional DOCX document."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    run_a = data.get("run_a", {})
    run_b = data.get("run_b", {})
    comparison = data.get("comparison", {})

    # --- Title ---
    title = doc.add_heading("CRM Intelligence — Comparison Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # --- Metadata ---
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_run = meta.add_run(
        f"{run_a.get('company', '')} · {run_a.get('vertical_code', '')}\n"
        f"Period A: {run_a.get('date_range_start', '?')} — {run_a.get('date_range_end', '?')} "
        f"({run_a.get('campaign_count', 0)} campaigns)\n"
        f"Period B: {run_b.get('date_range_start', '?')} — {run_b.get('date_range_end', '?')} "
        f"({run_b.get('campaign_count', 0)} campaigns)"
    )
    meta_run.font.size = Pt(10)
    meta_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()  # spacer

    # --- Executive Summary ---
    doc.add_heading("Executive Comparison Summary", level=1)
    doc.add_paragraph(comparison.get("summary", ""))

    # --- Context Note ---
    if comparison.get("context_note"):
        note_para = doc.add_paragraph()
        note_run = note_para.add_run(f"Note: {comparison['context_note']}")
        note_run.font.italic = True
        note_run.font.size = Pt(10)
        note_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # --- Metrics Delta Table ---
    doc.add_heading("Key Metrics Change", level=1)
    delta = comparison.get("metrics_delta", {})

    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    headers = ["CTR", "CTOR", "Conversions", "Volume (Sent)", "Delivery Rate"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h

    row = table.add_row()
    values = [
        f"{delta.get('ctr_change', 0):+.1f}pp",
        f"{delta.get('ctor_change', 0):+.1f}pp",
        f"{delta.get('conversion_change', 0):+,}",
        f"{delta.get('sent_change', 0):+,}",
        f"{delta.get('delivery_rate_change', 0):+.1f}pp",
    ]
    for i, v in enumerate(values):
        row.cells[i].text = v

    # --- Period Comparison Table ---
    doc.add_heading("Period Overview", level=1)
    table2 = doc.add_table(rows=1, cols=3)
    table2.style = "Light Grid Accent 1"
    table2.rows[0].cells[0].text = "Metric"
    table2.rows[0].cells[1].text = "Period A"
    table2.rows[0].cells[2].text = "Period B"

    overall_a = run_a.get("overall", {})
    overall_b = run_b.get("overall", {})

    metric_rows = [
        ("Campaigns", str(run_a.get("campaign_count", 0)), str(run_b.get("campaign_count", 0))),
        ("Total Sent", f"{overall_a.get('total_sent', 0):,}", f"{overall_b.get('total_sent', 0):,}"),
        ("CTR", f"{overall_a.get('overall_ctr', 0)}%", f"{overall_b.get('overall_ctr', 0)}%"),
        ("CTOR", f"{overall_a.get('overall_ctor', 0)}%", f"{overall_b.get('overall_ctor', 0)}%"),
        ("Conversions", f"{overall_a.get('total_influenced_conversions', 0):,}", f"{overall_b.get('total_influenced_conversions', 0):,}"),
        ("Delivery Rate", f"{overall_a.get('overall_delivery_rate', 0)}%", f"{overall_b.get('overall_delivery_rate', 0)}%"),
    ]
    for label, val_a, val_b in metric_rows:
        r = table2.add_row()
        r.cells[0].text = label
        r.cells[1].text = val_a
        r.cells[2].text = val_b

    # --- Improvements ---
    improvements = comparison.get("improvements", [])
    if improvements:
        doc.add_heading("Improvements", level=1)
        for item in improvements:
            doc.add_paragraph(item, style="List Bullet")

    # --- Declines ---
    declines = comparison.get("declines", [])
    if declines:
        doc.add_heading("Declines", level=1)
        for item in declines:
            doc.add_paragraph(item, style="List Bullet")

    # --- Strategy Shifts ---
    shifts = comparison.get("strategy_shifts", [])
    if shifts:
        doc.add_heading("Strategy Shifts", level=1)
        for item in shifts:
            doc.add_paragraph(item, style="List Bullet")

    # --- Recommendation ---
    doc.add_heading("Recommendation", level=1)
    doc.add_paragraph(comparison.get("recommendation", ""))

    # --- Footer ---
    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("Generated by Attributics CRM Intelligence Engine")
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Save
    doc.save(str(output_path))
    logger.info(f"Comparison DOCX saved: {output_path}")
