"""
DOCX Report Renderer — generates professional CRM Intelligence Reports.

Uses python-docx to produce a complete executive report with:
1. Cover page (company, vertical, date range, branded)
2. Executive Summary (LLM-narrated)
3. Channel Performance (table + narrative)
4. Offer/Campaign Type Analysis (table + narrative)
5. Creative Intelligence (opening style, tone, CTA strength)
6. Keywords Analysis (theme keywords performance)
7. Emoji Analysis (emoji usage correlation with engagement)
8. Headers & Message Arrangement (structure + length analysis)
9. Timing Analysis (day + hour tables)
10. Top & Bottom Performers (detailed breakdowns)
11. Recommendations (prioritized list)
12. Methodology & Definitions (appendix)

Design: The renderer ONLY reads from Facts + NarratedInsights.
It never computes metrics — those come pre-computed.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from docx.table import Table

from crm_intelligence.config import OUTPUT_DIR
from crm_intelligence.llm.narrator import NarratedInsights
from crm_intelligence.models.facts import Facts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

# Brand colors
COLOR_PRIMARY = RGBColor(0x1B, 0x36, 0x5F)  # Deep navy
COLOR_SECONDARY = RGBColor(0x2E, 0x86, 0xAB)  # Teal accent
COLOR_LIGHT_BG = RGBColor(0xF0, 0xF4, 0xF8)  # Light table header
COLOR_SUCCESS = RGBColor(0x27, 0xAE, 0x60)  # Green for strong
COLOR_WARNING = RGBColor(0xF3, 0x9C, 0x12)  # Orange for moderate
COLOR_DANGER = RGBColor(0xE7, 0x4C, 0x3C)  # Red for underperforming

FONT_BODY = "Calibri"
FONT_HEADING = "Calibri Light"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _set_cell_shading(cell, color_hex: str) -> None:
    """Set cell background color."""
    shading_elm = OxmlElement("w:shd")
    shading_elm.set(qn("w:fill"), color_hex)
    shading_elm.set(qn("w:val"), "clear")
    cell._tc.get_or_add_tcPr().append(shading_elm)


def _set_table_style(table: Table) -> None:
    """Apply consistent styling to a table."""
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row styling
    if table.rows:
        for cell in table.rows[0].cells:
            _set_cell_shading(cell, "1B365F")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    run.font.bold = True
                    run.font.size = Pt(9)


def _add_verdict_color(paragraph, verdict: str) -> None:
    """Add a colored verdict indicator."""
    run = paragraph.add_run(f" [{verdict.upper()}]")
    run.font.size = Pt(8)
    run.font.bold = True
    if verdict == "strong":
        run.font.color.rgb = COLOR_SUCCESS
    elif verdict == "adequate":
        run.font.color.rgb = COLOR_WARNING
    else:
        run.font.color.rgb = COLOR_DANGER


def _add_spacer(doc: Document, height_pt: int = 12) -> None:
    """Add vertical space."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(height_pt)
    p.paragraph_format.space_before = Pt(0)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def _render_cover_page(doc: Document, facts: Facts) -> None:
    """Render the cover page with branding."""
    # Add spacing to push content down
    for _ in range(4):
        doc.add_paragraph()

    # Title
    title = doc.add_heading("CRM Intelligence Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = COLOR_PRIMARY
        run.font.size = Pt(32)

    _add_spacer(doc, 20)

    # Company name
    company_para = doc.add_paragraph()
    company_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = company_para.add_run(facts.meta.company)
    run.font.size = Pt(24)
    run.font.color.rgb = COLOR_SECONDARY

    # Vertical
    vertical_para = doc.add_paragraph()
    vertical_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = vertical_para.add_run(facts.meta.vertical)
    run.font.size = Pt(16)
    run.font.color.rgb = COLOR_PRIMARY

    _add_spacer(doc, 40)

    # Date range
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_str = (
        f"{facts.meta.date_range_start.strftime('%B %d, %Y')} — "
        f"{facts.meta.date_range_end.strftime('%B %d, %Y')}"
    )
    run = date_para.add_run(date_str)
    run.font.size = Pt(14)

    # Campaign count
    count_para = doc.add_paragraph()
    count_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = count_para.add_run(
        f"{facts.meta.campaign_count} Campaigns | "
        f"{', '.join(facts.meta.channels)} | "
        f"{facts.meta.total_sent:,} Total Reach"
    )
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    _add_spacer(doc, 60)

    # Generated timestamp
    gen_para = doc.add_paragraph()
    gen_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = gen_para.add_run(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    run = gen_para.add_run("\nPowered by Attributics CRM Intelligence Engine")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Page break
    doc.add_page_break()


def _render_executive_summary(doc: Document, insights: NarratedInsights, facts: Facts) -> None:
    """Render executive summary section."""
    doc.add_heading("Executive Summary", level=1)

    # Key metrics bar (quick reference)
    metrics_para = doc.add_paragraph()
    metrics_para.paragraph_format.space_after = Pt(12)
    metrics = [
        f"CTR: {facts.overall.overall_ctr}%",
        f"CTOR: {facts.overall.overall_ctor}%",
        f"Delivery: {facts.overall.overall_delivery_rate}%",
        f"Conversions: {facts.overall.total_influenced_conversions:,}",
    ]
    run = metrics_para.add_run("  |  ".join(metrics))
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = COLOR_SECONDARY

    # Narrative
    for paragraph_text in insights.executive_summary.split("\n\n"):
        if paragraph_text.strip():
            p = doc.add_paragraph(paragraph_text.strip())
            p.paragraph_format.space_after = Pt(8)

    doc.add_page_break()


def _render_channel_performance(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render channel performance table and insights."""
    doc.add_heading("Channel Performance", level=1)

    # Table
    headers = ["Channel", "Campaigns", "Sent", "CTR %", "CTOR %", "Delivery %", "Conversions"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    # Header row
    for i, header in enumerate(headers):
        table.rows[0].cells[i].text = header

    # Data rows
    for ch in facts.by_channel:
        row = table.add_row()
        row.cells[0].text = ch.channel
        row.cells[1].text = str(ch.campaign_count)
        row.cells[2].text = f"{ch.total_sent:,}"
        row.cells[3].text = f"{ch.ctr}"
        row.cells[4].text = f"{ch.ctor}"
        row.cells[5].text = f"{ch.delivery_rate}"
        row.cells[6].text = f"{ch.total_influenced_conversions:,}"

    _set_table_style(table)
    _add_spacer(doc, 16)

    # Channel narratives
    for ch_insight in insights.channel_insights:
        p = doc.add_paragraph()
        run = p.add_run(f"{ch_insight.get('channel', 'N/A')}: ")
        run.font.bold = True
        p.add_run(ch_insight.get("narrative", ""))
        if "verdict" in ch_insight:
            _add_verdict_color(p, ch_insight["verdict"])

    doc.add_page_break()


def _render_offer_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render offer/campaign type analysis."""
    doc.add_heading("Offer Type Analysis", level=1)

    # Table
    headers = ["Offer Type", "Campaigns", "CTR %", "CTOR %", "CVR %", "Conversions"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for i, header in enumerate(headers):
        table.rows[0].cells[i].text = header

    for offer in facts.by_offer:
        row = table.add_row()
        row.cells[0].text = offer.offer
        row.cells[1].text = str(offer.campaign_count)
        row.cells[2].text = f"{offer.ctr}"
        row.cells[3].text = f"{offer.ctor}"
        row.cells[4].text = f"{offer.cvr_influenced}"
        row.cells[5].text = f"{offer.total_influenced_conversions:,}"

    _set_table_style(table)
    _add_spacer(doc, 16)

    # Offer narratives
    for offer_insight in insights.offer_insights:
        p = doc.add_paragraph()
        run = p.add_run(f"{offer_insight.get('offer', 'N/A')}: ")
        run.font.bold = True
        p.add_run(offer_insight.get("narrative", ""))
        if "verdict" in offer_insight:
            _add_verdict_color(p, offer_insight["verdict"])

    doc.add_page_break()


def _render_label_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render label/category analysis section."""
    doc.add_heading("Category Analysis", level=1)

    # Table
    headers = ["Category", "Campaigns", "Sent", "Viewed %", "CTR %", "CTOR %", "Conversions"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for i, header in enumerate(headers):
        table.rows[0].cells[i].text = header

    for lb in facts.by_label[:20]:  # Top 20 labels
        row = table.add_row()
        row.cells[0].text = lb.label.replace("_", " ").title()
        row.cells[1].text = str(lb.campaign_count)
        row.cells[2].text = f"{lb.total_sent:,}"
        row.cells[3].text = f"{lb.viewed_pct}"
        row.cells[4].text = f"{lb.ctr}"
        row.cells[5].text = f"{lb.ctor}"
        row.cells[6].text = f"{lb.total_influenced_conversions:,}"

    _set_table_style(table)
    _add_spacer(doc, 16)

    # Label narratives (from L2)
    for label_insight in getattr(insights, "label_insights", []):
        p = doc.add_paragraph()
        run = p.add_run(f"{label_insight.get('label', 'N/A')}: ")
        run.font.bold = True
        p.add_run(label_insight.get("narrative", ""))
        if "verdict" in label_insight:
            _add_verdict_color(p, label_insight["verdict"])

    doc.add_page_break()


def _render_creative_intelligence(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render creative intelligence section (classification-based insights)."""
    doc.add_heading("Creative Intelligence", level=1)

    creative = insights.creative_insights

    # Overall creative verdict (highlighted)
    if creative.get("overall_creative_verdict"):
        verdict_para = doc.add_paragraph()
        run = verdict_para.add_run("Key Finding: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        verdict_para.add_run(creative["overall_creative_verdict"])
        _add_spacer(doc, 12)

    # Opening Style subsection
    if facts.by_opening_style:
        doc.add_heading("Opening Style Performance", level=2)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for i, h in enumerate(["Opening Style", "Campaigns", "CTR %", "CTOR %"]):
            table.rows[0].cells[i].text = h
        for item in facts.by_opening_style:
            row = table.add_row()
            row.cells[0].text = item.label.replace("_", " ").title()
            row.cells[1].text = str(item.campaign_count)
            row.cells[2].text = f"{item.ctr}"
            row.cells[3].text = f"{item.ctor}"
        _set_table_style(table)

        if creative.get("opening_style_narrative"):
            p = doc.add_paragraph(creative["opening_style_narrative"])
            p.paragraph_format.space_before = Pt(8)

    # Tone subsection
    if facts.by_tone:
        _add_spacer(doc, 8)
        doc.add_heading("Tone Performance", level=2)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for i, h in enumerate(["Tone", "Campaigns", "CTR %", "CTOR %"]):
            table.rows[0].cells[i].text = h
        for item in facts.by_tone:
            row = table.add_row()
            row.cells[0].text = item.label.replace("_", " ").title()
            row.cells[1].text = str(item.campaign_count)
            row.cells[2].text = f"{item.ctr}"
            row.cells[3].text = f"{item.ctor}"
        _set_table_style(table)

        if creative.get("tone_narrative"):
            p = doc.add_paragraph(creative["tone_narrative"])
            p.paragraph_format.space_before = Pt(8)

    # CTA Strength subsection
    if facts.by_cta_strength:
        _add_spacer(doc, 8)
        doc.add_heading("CTA Strength Performance", level=2)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for i, h in enumerate(["CTA Strength", "Campaigns", "CTR %", "Conversions"]):
            table.rows[0].cells[i].text = h
        for item in facts.by_cta_strength:
            row = table.add_row()
            row.cells[0].text = item.label.title()
            row.cells[1].text = str(item.campaign_count)
            row.cells[2].text = f"{item.ctr}"
            row.cells[3].text = f"{item.total_influenced_conversions:,}"
        _set_table_style(table)

        if creative.get("cta_narrative"):
            p = doc.add_paragraph(creative["cta_narrative"])
            p.paragraph_format.space_before = Pt(8)

    doc.add_page_break()


def _render_keywords_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render keywords analysis section — shows which message themes drive performance."""
    doc.add_heading("Keywords Analysis", level=1)

    keyword_insights = insights.keyword_insights

    # Intro narrative
    if keyword_insights.get("top_keywords_narrative"):
        p = doc.add_paragraph(keyword_insights["top_keywords_narrative"])
        p.paragraph_format.space_after = Pt(12)

    # Keywords performance table
    if facts.by_keyword:
        headers = ["Keyword Theme", "Campaigns", "Total Sent", "Clicked", "CTR %", "CTOR %", "Conversions"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h

        for kw in facts.by_keyword[:15]:  # Top 15 keywords
            row = table.add_row()
            row.cells[0].text = kw.keyword.title()
            row.cells[1].text = str(kw.campaign_count)
            row.cells[2].text = f"{kw.total_sent:,}"
            row.cells[3].text = f"{kw.total_clicked:,}"
            row.cells[4].text = f"{kw.ctr}"
            row.cells[5].text = f"{kw.ctor}"
            row.cells[6].text = f"{kw.total_influenced_conversions:,}"
        _set_table_style(table)

        _add_spacer(doc, 12)

    # Underperforming keywords narrative
    if keyword_insights.get("underperforming_keywords"):
        p = doc.add_paragraph()
        run = p.add_run("Underperforming Themes: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_WARNING
        p.add_run(keyword_insights["underperforming_keywords"])
        _add_spacer(doc, 8)

    # Recommendation
    if keyword_insights.get("keyword_recommendation"):
        p = doc.add_paragraph()
        run = p.add_run("Recommendation: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        p.add_run(keyword_insights["keyword_recommendation"])

    doc.add_page_break()


def _render_emoji_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render emoji analysis section — correlates emoji usage levels with performance."""
    doc.add_heading("Emoji Analysis", level=1)

    emoji_insights = insights.emoji_insights

    # Narrative intro
    if emoji_insights.get("emoji_usage_narrative"):
        p = doc.add_paragraph(emoji_insights["emoji_usage_narrative"])
        p.paragraph_format.space_after = Pt(12)

    # Emoji bucket performance table
    if facts.by_emoji_bucket:
        headers = ["Emoji Usage Level", "Campaigns", "CTR %", "CTOR %", "Conversions"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h

        for bucket in facts.by_emoji_bucket:
            row = table.add_row()
            row.cells[0].text = bucket.label.title()
            row.cells[1].text = str(bucket.campaign_count)
            row.cells[2].text = f"{bucket.ctr}"
            row.cells[3].text = f"{bucket.ctor}"
            row.cells[4].text = f"{bucket.total_influenced_conversions:,}"
        _set_table_style(table)

        _add_spacer(doc, 12)

    # Optimal level callout
    if emoji_insights.get("optimal_emoji_level"):
        p = doc.add_paragraph()
        run = p.add_run("Optimal Level: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_SUCCESS
        p.add_run(emoji_insights["optimal_emoji_level"])
        _add_spacer(doc, 8)

    # Recommendation
    if emoji_insights.get("emoji_recommendation"):
        p = doc.add_paragraph()
        run = p.add_run("Recommendation: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        p.add_run(emoji_insights["emoji_recommendation"])

    doc.add_page_break()


def _render_message_structure_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render headers & message arrangement analysis."""
    doc.add_heading("Headers & Message Arrangement", level=1)

    structure_insights = insights.message_structure_insights

    # Narrative intro
    if structure_insights.get("structure_narrative"):
        p = doc.add_paragraph(structure_insights["structure_narrative"])
        p.paragraph_format.space_after = Pt(12)

    # Message structure performance table
    if facts.by_message_structure:
        doc.add_heading("Message Arrangement Performance", level=2)
        headers = ["Arrangement", "Campaigns", "CTR %", "CTOR %", "Conversions"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h

        structure_labels = {
            "header_body_cta": "Header + Body + CTA",
            "body_cta": "Body + CTA (No Header)",
            "greeting_body_cta": "Greeting + Body + CTA",
            "single_block": "Single Block",
            "multi_section": "Multi-Section",
        }

        for item in facts.by_message_structure:
            row = table.add_row()
            row.cells[0].text = structure_labels.get(item.label, item.label.replace("_", " ").title())
            row.cells[1].text = str(item.campaign_count)
            row.cells[2].text = f"{item.ctr}"
            row.cells[3].text = f"{item.ctor}"
            row.cells[4].text = f"{item.total_influenced_conversions:,}"
        _set_table_style(table)

        _add_spacer(doc, 16)

    # Message length performance table
    if facts.by_message_length:
        doc.add_heading("Message Length Performance", level=2)
        headers = ["Length", "Campaigns", "CTR %", "CTOR %", "Conversions"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h

        length_labels = {
            "short": "Short (<50 words)",
            "medium": "Medium (50-100 words)",
            "long": "Long (100+ words)",
        }

        for item in facts.by_message_length:
            row = table.add_row()
            row.cells[0].text = length_labels.get(item.label, item.label.title())
            row.cells[1].text = str(item.campaign_count)
            row.cells[2].text = f"{item.ctr}"
            row.cells[3].text = f"{item.ctor}"
            row.cells[4].text = f"{item.total_influenced_conversions:,}"
        _set_table_style(table)

        _add_spacer(doc, 12)

        if structure_insights.get("length_narrative"):
            p = doc.add_paragraph(structure_insights["length_narrative"])
            p.paragraph_format.space_before = Pt(8)

    # Structure recommendation
    if structure_insights.get("structure_recommendation"):
        _add_spacer(doc, 8)
        p = doc.add_paragraph()
        run = p.add_run("Ideal Message Blueprint: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        p.add_run(structure_insights["structure_recommendation"])

    doc.add_page_break()


def _render_timing_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render timing analysis (day + hour)."""
    doc.add_heading("Timing Analysis", level=1)

    timing = insights.timing_insights

    # Day of week table
    doc.add_heading("Day of Week Performance", level=2)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for i, h in enumerate(["Day", "Campaigns", "Sent", "CTR %", "Conversions"]):
        table.rows[0].cells[i].text = h
    for day in facts.by_day:
        row = table.add_row()
        row.cells[0].text = day.bucket
        row.cells[1].text = str(day.campaign_count)
        row.cells[2].text = f"{day.total_sent:,}"
        row.cells[3].text = f"{day.ctr}"
        row.cells[4].text = f"{day.total_influenced_conversions:,}"
    _set_table_style(table)

    if timing.get("best_days"):
        p = doc.add_paragraph(timing["best_days"])
        p.paragraph_format.space_before = Pt(8)

    _add_spacer(doc, 16)

    # Hour bucket table
    doc.add_heading("Time of Day Performance", level=2)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for i, h in enumerate(["Time Slot", "Campaigns", "Sent", "CTR %", "Conversions"]):
        table.rows[0].cells[i].text = h
    for hour in facts.by_hour:
        row = table.add_row()
        row.cells[0].text = hour.bucket
        row.cells[1].text = str(hour.campaign_count)
        row.cells[2].text = f"{hour.total_sent:,}"
        row.cells[3].text = f"{hour.ctr}"
        row.cells[4].text = f"{hour.total_influenced_conversions:,}"
    _set_table_style(table)

    if timing.get("best_hours"):
        p = doc.add_paragraph(timing["best_hours"])
        p.paragraph_format.space_before = Pt(8)

    if timing.get("timing_recommendation"):
        _add_spacer(doc, 8)
        p = doc.add_paragraph()
        run = p.add_run("Recommendation: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        p.add_run(timing["timing_recommendation"])

    doc.add_page_break()


def _render_performers(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render top and bottom performer sections."""
    doc.add_heading("Campaign Performance Rankings", level=1)

    # Top performers
    doc.add_heading("Top Performers", level=2)

    if insights.top_performer_analysis:
        p = doc.add_paragraph(insights.top_performer_analysis)
        p.paragraph_format.space_after = Pt(12)
        p.runs[0].font.italic = True if p.runs else None

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    for i, h in enumerate(["#", "Campaign", "Channel", "Offer", "CTR %", "Conv"]):
        table.rows[0].cells[i].text = h

    for i, tp in enumerate(facts.top_performers, 1):
        row = table.add_row()
        row.cells[0].text = str(i)
        row.cells[1].text = tp.campaign_name[:40]
        row.cells[2].text = tp.channel
        row.cells[3].text = tp.offer or "—"
        row.cells[4].text = f"{tp.ctr}"
        row.cells[5].text = str(tp.influenced_conversions)
    _set_table_style(table)

    _add_spacer(doc, 20)

    # Bottom performers
    doc.add_heading("Underperformers (Optimization Opportunities)", level=2)

    if insights.bottom_performer_analysis:
        p = doc.add_paragraph(insights.bottom_performer_analysis)
        p.paragraph_format.space_after = Pt(12)
        p.runs[0].font.italic = True if p.runs else None

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    for i, h in enumerate(["#", "Campaign", "Channel", "Offer", "CTR %", "Conv"]):
        table.rows[0].cells[i].text = h

    for i, bp in enumerate(facts.bottom_performers, 1):
        row = table.add_row()
        row.cells[0].text = str(i)
        row.cells[1].text = bp.campaign_name[:40]
        row.cells[2].text = bp.channel
        row.cells[3].text = bp.offer or "—"
        row.cells[4].text = f"{bp.ctr}"
        row.cells[5].text = str(bp.influenced_conversions)
    _set_table_style(table)

    doc.add_page_break()


def _render_segment_analysis(doc: Document, facts: Facts, insights: NarratedInsights) -> None:
    """Render segment analysis section."""
    doc.add_heading("Segment Analysis", level=1)

    # Table
    headers = ["Segment", "Campaigns", "Total Sent", "CTR %", "CTOR %"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h

    for seg in facts.by_segment:
        row = table.add_row()
        row.cells[0].text = seg.segment[:50]
        row.cells[1].text = str(seg.campaign_count)
        row.cells[2].text = f"{seg.total_sent:,}"
        row.cells[3].text = f"{seg.ctr}"
        row.cells[4].text = f"{seg.ctor}"
    _set_table_style(table)

    _add_spacer(doc, 12)

    # Segment narratives
    for seg_insight in insights.segment_insights:
        p = doc.add_paragraph()
        run = p.add_run(f"{seg_insight.get('segment', 'N/A')[:40]}: ")
        run.font.bold = True
        p.add_run(seg_insight.get("narrative", ""))
        if seg_insight.get("opportunity"):
            opp_para = doc.add_paragraph()
            opp_para.paragraph_format.left_indent = Cm(1)
            run = opp_para.add_run("Opportunity: ")
            run.font.italic = True
            run.font.color.rgb = COLOR_SECONDARY
            opp_para.add_run(seg_insight["opportunity"])

    doc.add_page_break()


def _render_recommendations(doc: Document, insights: NarratedInsights) -> None:
    """Render prioritized recommendations."""
    doc.add_heading("Recommendations", level=1)

    intro = doc.add_paragraph(
        "The following recommendations are prioritized by expected impact "
        "and supported by specific data points from this analysis."
    )
    intro.paragraph_format.space_after = Pt(16)

    for rec in insights.recommendations:
        # Priority badge + action
        p = doc.add_paragraph()
        priority = rec.get("priority", "—")
        run = p.add_run(f"Priority {priority}: ")
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        run.font.size = Pt(11)
        p.add_run(rec.get("action", ""))

        # Expected impact
        if rec.get("expected_impact"):
            impact_p = doc.add_paragraph()
            impact_p.paragraph_format.left_indent = Cm(1)
            run = impact_p.add_run("Expected Impact: ")
            run.font.bold = True
            run.font.size = Pt(9)
            run2 = impact_p.add_run(rec["expected_impact"])
            run2.font.size = Pt(9)

        # Rationale
        if rec.get("rationale"):
            rat_p = doc.add_paragraph()
            rat_p.paragraph_format.left_indent = Cm(1)
            run = rat_p.add_run("Data Support: ")
            run.font.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            run2 = rat_p.add_run(rec["rationale"])
            run2.font.size = Pt(9)
            run2.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        _add_spacer(doc, 8)

    doc.add_page_break()


def _render_methodology(doc: Document, facts: Facts) -> None:
    """Render methodology and definitions appendix."""
    doc.add_heading("Methodology & Definitions", level=1)

    # Metrics definitions
    doc.add_heading("Key Metrics", level=2)
    definitions = [
        ("CTR (Click-Through Rate)", "Clicked / Sent × 100. Measures initial message engagement."),
        ("CTOR (Click-to-Open Rate)", "Clicked / Viewed × 100. Measures content quality among openers."),
        ("Delivery Rate", "Delivered / Sent × 100. Platform delivery effectiveness."),
        ("CVR (Conversion Rate)", "Influenced Conversions / Sent × 100. Business impact per impression."),
        (
            "Composite Score",
            "Weighted blend: 40% CTR + 30% CTOR + 30% CVR. "
            "Used for campaign ranking (balances engagement + business impact).",
        ),
    ]

    for term, definition in definitions:
        p = doc.add_paragraph()
        run = p.add_run(f"{term}: ")
        run.font.bold = True
        p.add_run(definition)

    _add_spacer(doc, 12)

    # Analysis scope
    doc.add_heading("Analysis Scope", level=2)
    scope_items = [
        f"Period: {facts.meta.date_range_start} to {facts.meta.date_range_end}",
        f"Campaigns analyzed: {facts.meta.campaign_count}",
        f"Channels: {', '.join(facts.meta.channels)}",
        f"Total audience reached: {facts.meta.total_sent:,}",
    ]
    for item in scope_items:
        doc.add_paragraph(item)

    _add_spacer(doc, 12)

    # Methodology notes
    doc.add_heading("Notes", level=2)
    notes = [
        "All metrics are computed deterministically from raw platform data.",
        "Creative classifications (opening style, tone, CTA strength) are produced by Claude AI "
        "and represent qualitative assessments of message content.",
        "Push Notification delivery uses 'Viewed' as proxy (platform reports 0 delivered).",
        "Campaign rankings use a composite score to balance engagement quality with business outcomes.",
    ]
    for note in notes:
        doc.add_paragraph(note)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_report(
    facts: Facts,
    insights: NarratedInsights,
    output_filename: Optional[str] = None,
    selected_sections: Optional[list[str]] = None,
) -> Path:
    """
    Render a complete CRM Intelligence Report as DOCX.

    Args:
        facts: Complete computed Facts object.
        insights: LLM-narrated insights.
        output_filename: Optional custom filename. Defaults to
            "{company}_{vertical}_{date}_CRM_Report.docx"

    Returns:
        Path to the generated DOCX file.
    """
    logger.info(f"Rendering report for {facts.meta.company} / {facts.meta.vertical}")

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = FONT_BODY
    font.size = Pt(10)

    # Set narrow margins for more content space
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Determine which sections to render
    secs = set(selected_sections) if selected_sections else None

    # Render sections based on selection (cover + exec summary always included)
    _render_cover_page(doc, facts)
    _render_executive_summary(doc, insights, facts)

    # Section dispatch — ordered for report flow
    if secs is None or "channel_performance" in secs:
        if facts.by_channel and len(facts.by_channel) > 1:
            _render_channel_performance(doc, facts, insights)

    if secs is None or "offer_analysis" in secs:
        if facts.by_offer:
            _render_offer_analysis(doc, facts, insights)

    if secs is None or "label_analysis" in secs:
        if facts.by_label:
            _render_label_analysis(doc, facts, insights)

    if secs is None or "creative_intelligence" in secs:
        if facts.by_opening_style or facts.by_tone or facts.by_cta_strength:
            _render_creative_intelligence(doc, facts, insights)

    if secs is None or "keywords" in secs:
        if facts.by_keyword:
            _render_keywords_analysis(doc, facts, insights)

    if secs is None or "emoji" in secs:
        if facts.by_emoji_bucket:
            _render_emoji_analysis(doc, facts, insights)

    if secs is None or "message_structure" in secs:
        if facts.by_message_structure or facts.by_message_length:
            _render_message_structure_analysis(doc, facts, insights)

    if secs is None or "timing" in secs:
        _render_timing_analysis(doc, facts, insights)

    if secs is None or "performers" in secs:
        _render_performers(doc, facts, insights)

    if secs is None or "recommendations" in secs:
        _render_recommendations(doc, insights)

    _render_methodology(doc, facts)

    # Generate filename
    if output_filename is None:
        date_str = facts.meta.date_range_end.strftime("%b%Y")
        company_slug = facts.meta.company.replace(" ", "")
        vertical_slug = facts.meta.vertical.replace(" ", "")
        output_filename = f"{company_slug}_{vertical_slug}_{date_str}_CRM_Report.docx"

    output_path = OUTPUT_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc.save(str(output_path))
    logger.info(f"Report saved: {output_path}")

    return output_path
