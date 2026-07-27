"""
CRM Intelligence Engine - Application entry point and orchestrator.

Coordinates the full analysis pipeline:
  1. Intake: receive file path, detect platform, validate structure
  2. Context: load business profile + vertical profile (create if first run)
  3. Adapt: platform adapter produces CanonicalCampaign objects
  4. Analytics: deterministic computation produces Facts object
  5. Intelligence L1: LLM classification of messages (temp=0)
  6. Merge: integrate classifications back into Facts
  7. Intelligence L2: LLM narration from Facts + profiles (temp=0.3)
  8. Render: produce DOCX report
  9. Persist: save run metadata, facts, insights

Usage:
    python -m crm_intelligence.main <file_path> --company NAME --vertical CODE
"""

import argparse
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from crm_intelligence import __version__
from crm_intelligence.adapters import adapt_file
from crm_intelligence.analytics import compute_facts
from crm_intelligence.config import MIN_CAMPAIGNS_FOR_ANALYSIS
from crm_intelligence.llm.classifier import classify_campaigns
from crm_intelligence.llm.client import BedrockClientError, usage as token_usage
from crm_intelligence.llm.merge import merge_classifications
from crm_intelligence.llm.narrator import narrate_facts
from crm_intelligence.logging_config import setup_logging
from crm_intelligence.models.profile import BusinessProfile, VerticalProfile
from crm_intelligence.models.run import Run, RunStatus
from crm_intelligence.renderer import render_report
from crm_intelligence.sections import (
    ALL_SECTION_IDS,
    get_required_l1_dimensions,
    needs_l1,
    needs_l2,
)
from crm_intelligence.storage import (
    get_last_successful_run,
    load_facts,
    load_profile,
    save_facts,
    save_insights,
    save_profile,
    save_run,
)

logger = logging.getLogger(__name__)


def run_pipeline(
    file_path: Path,
    company: str,
    vertical_code: str,
    industry: str = "Hospitality & Leisure",
    skip_llm: bool = False,
    selected_sections: Optional[list[str]] = None,
    progress_callback: Optional[object] = None,
) -> Path:
    """
    Execute the complete CRM Intelligence pipeline.

    Args:
        file_path: Path to the raw CRM export file (CSV or Excel).
        company: Company name (used for profile lookup/creation).
        vertical_code: Vertical identifier (e.g., "HFRP", "Loyalty").
        industry: Industry vertical (for new profile creation).
        skip_llm: If True, skip LLM calls (useful for testing analytics only).
        selected_sections: List of section IDs to include in report. If None,
            uses profile's stored selections, or all sections if none stored.
        progress_callback: Optional callable(step: int, total: int, message: str, detail: str|None)
            called after each pipeline stage completes. Used for real-time progress.

    Returns:
        Path to the generated DOCX report.

    Raises:
        FileNotFoundError: If input file doesn't exist.
        ValueError: If file can't be adapted or has too few campaigns.
    """

    def _progress(step: int, total: int, message: str, detail: str = None):
        """Report progress if callback is available."""
        if progress_callback:
            try:
                progress_callback(step, total, message, detail)
            except Exception:
                pass  # Never let progress reporting break the pipeline
    run_id = str(uuid.uuid4())[:8]
    run = Run(
        run_id=run_id,
        company=company,
        vertical_code=vertical_code,
        source_platform="detecting...",
        source_filename=file_path.name,
        status=RunStatus.RUNNING,
    )

    logger.info("=" * 60)
    logger.info(f"CRM Intelligence Engine v{__version__}")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Company: {company} | Vertical: {vertical_code}")
    logger.info(f"Input: {file_path.name}")
    logger.info("=" * 60)

    try:
        # Step 1: Load/create business profile
        _progress(1, 8, "Loading business profile...", None)
        logger.info("Step 1/8: Loading business profile...")
        profile = load_profile(company)
        if profile is None:
            logger.info(f"  No existing profile for '{company}'. Creating new profile.")
            profile = BusinessProfile(
                company_name=company,
                industry=industry,
            )
            save_profile(profile)
        else:
            logger.info(f"  Profile loaded: {profile.company_name} ({profile.industry})")

        # Get or create vertical profile
        vertical_profile = profile.get_vertical(vertical_code)
        if vertical_profile is None:
            vertical_profile = VerticalProfile(name=vertical_code, code=vertical_code)
            if profile.verticals is None:
                profile.verticals = []
            profile.verticals.append(vertical_profile)
            save_profile(profile)
            logger.info(f"  Created vertical profile: {vertical_code}")

        # Resolve selected sections (CLI > profile > all)
        sections = selected_sections
        if sections is None and profile.selected_sections:
            sections = profile.selected_sections
            logger.info(f"  Using profile sections: {sections}")
        elif sections:
            logger.info(f"  Using CLI sections: {sections}")
        else:
            logger.info("  No sections specified — computing all")

        # Step 2: Adapt the file
        _progress(2, 8, "Parsing & normalizing file...", f"File: {file_path.name}")
        logger.info("Step 2/8: Adapting raw export...")
        result = adapt_file(file_path)

        run.source_platform = "clevertap"
        run.campaign_count = result.success_count

        logger.info(
            f"  Adapter result: {result.success_count}/{result.total_rows} campaigns "
            f"({result.success_rate:.1f}% success)"
        )
        if result.errors:
            logger.warning(f"  {result.error_count} rows had errors:")
            for err in result.errors[:3]:
                logger.warning(f"    {err}")

        if result.success_count < MIN_CAMPAIGNS_FOR_ANALYSIS:
            raise ValueError(
                f"Only {result.success_count} campaigns parsed successfully. "
                f"Minimum required: {MIN_CAMPAIGNS_FOR_ANALYSIS}. "
                f"Check adapter errors above."
            )

        campaigns = result.campaigns

        # Step 3: Compute analytics
        _progress(3, 8, "Computing analytics...", f"{result.success_count} campaigns loaded")
        logger.info("Step 3/8: Computing deterministic analytics...")

        prior_facts = None
        prior_run = get_last_successful_run(company, vertical_code)
        if prior_run:
            prior_facts = load_facts(prior_run.run_id)
            if prior_facts:
                logger.info(f"  Prior run found ({prior_run.run_id}) - will compute trends")

        facts = compute_facts(
            campaigns=campaigns,
            company=company,
            vertical=vertical_code,
            prior_facts=prior_facts,
            selected_sections=sections,
            label_separator=getattr(profile, "label_separator", "|") or "|",
        )

        run.channels = facts.meta.channels
        run.date_range_start = str(facts.meta.date_range_start)
        run.date_range_end = str(facts.meta.date_range_end)

        logger.info(
            f"  Facts computed: CTR={facts.overall.overall_ctr}%, "
            f"CTOR={facts.overall.overall_ctor}%, "
            f"Conversions={facts.overall.total_influenced_conversions}"
        )

        if skip_llm:
            # Skip LLM mode (for testing)
            _progress(4, 8, "LLM skipped (test mode)", None)
            logger.info("Step 4-6/8: SKIPPED (--skip-llm mode)")
            from crm_intelligence.llm.narrator import _fallback_narration
            insights = _fallback_narration(facts)
        else:
            # Step 4: LLM Classification (L1) — skip if no sections need it
            l1_dimensions = get_required_l1_dimensions(sections) if sections else None

            if sections and not needs_l1(sections):
                _progress(4, 8, "L1 classification skipped (not needed)", None)
                logger.info("Step 4-5/8: SKIPPED (no selected sections need L1)")
                classifications = []
            else:
                _progress(4, 8, "Classifying campaigns with AI...", "L1 — Claude Opus, temp=0")
                logger.info("Step 4/8: Classifying campaigns (L1 - Claude, temp=0)...")
                if l1_dimensions:
                    logger.info(f"  Dimensions: {l1_dimensions}")
                classifications = classify_campaigns(campaigns, dimensions=l1_dimensions)
                logger.info(f"  Classified {len(classifications)} campaigns")

                # Step 5: Merge classifications into Facts
                _progress(5, 8, "Merging classifications...", f"{len(classifications)} campaigns classified")
                logger.info("Step 5/8: Merging classifications into facts...")
                facts = merge_classifications(facts, campaigns, classifications)
                logger.info(
                    f"  Merged: {len(facts.by_opening_style)} opening styles, "
                    f"{len(facts.by_tone)} tones"
                )

            # Step 6: LLM Narration (L2)
            if sections and not needs_l2(sections):
                _progress(6, 8, "Narration skipped (not needed)", None)
                logger.info("Step 6/8: SKIPPED (no selected sections need L2)")
                from crm_intelligence.llm.narrator import _fallback_narration
                insights = _fallback_narration(facts)
            else:
                _progress(6, 8, "Generating narrative insights with AI...", "L2 — Claude Opus, temp=0.3")
                logger.info("Step 6/8: Narrating insights (L2 - Claude, temp=0.3)...")
                insights = narrate_facts(
                    facts, profile, vertical_profile, selected_sections=sections
                )
                logger.info("  Narration complete")

        # Step 7: Render DOCX
        _progress(7, 8, "Rendering executive report...", "Building DOCX with charts & tables")
        logger.info("Step 7/8: Rendering DOCX report...")
        report_path = render_report(facts, insights, selected_sections=sections)
        logger.info(f"  Report: {report_path}")

        # Step 8: Persist everything
        _progress(8, 8, "Saving report & artifacts...", None)
        logger.info("Step 8/8: Saving artifacts...")
        facts_path = save_facts(run_id, facts)
        run.facts_path = str(facts_path)
        run.report_path = str(report_path)

        insights_dict = {
            "executive_summary": insights.executive_summary,
            "channel_insights": insights.channel_insights,
            "offer_insights": insights.offer_insights,
            "creative_insights": insights.creative_insights,
            "timing_insights": insights.timing_insights,
            "segment_insights": insights.segment_insights,
            "top_performer_analysis": insights.top_performer_analysis,
            "bottom_performer_analysis": insights.bottom_performer_analysis,
            "recommendations": insights.recommendations,
            "trend_commentary": insights.trend_commentary,
        }
        insights_path = save_insights(run_id, insights_dict)
        run.insights_path = str(insights_path)

        run.status = RunStatus.COMPLETE
        run.completed_at = datetime.now()
        save_run(run)

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Report: {report_path}")
        logger.info(f"  Facts:  {facts_path}")
        if not skip_llm:
            logger.info(f"  Tokens: {token_usage}")
        logger.info("=" * 60)

        return report_path

    except Exception as e:
        run.status = RunStatus.FAILED
        run.error_message = str(e)[:500]
        save_run(run)
        logger.error(f"Pipeline failed: {e}")
        raise


def main() -> None:
    """CLI entry point for the CRM Intelligence Engine."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="CRM Intelligence Engine - analyze campaign exports, generate reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", type=Path, help="Path to CRM export file (CSV or Excel)")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--vertical", required=True, help="Vertical code (e.g., HFRP)")
    parser.add_argument("--industry", default="Hospitality & Leisure", help="Industry (for new profiles)")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM calls (analytics-only mode for testing)",
    )
    parser.add_argument(
        "--sections",
        type=str,
        default=None,
        help=(
            "Comma-separated section IDs to include in report. "
            f"Available: {', '.join(ALL_SECTION_IDS)}. "
            "If omitted, uses profile settings or computes all."
        ),
    )

    args = parser.parse_args()

    if not args.file.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    # Parse --sections
    sections_list: Optional[list[str]] = None
    if args.sections:
        sections_list = [s.strip() for s in args.sections.split(",") if s.strip()]
        # Validate
        invalid = [s for s in sections_list if s not in ALL_SECTION_IDS]
        if invalid:
            logger.error(
                f"Invalid section IDs: {invalid}. "
                f"Valid options: {ALL_SECTION_IDS}"
            )
            sys.exit(1)

    try:
        report_path = run_pipeline(
            file_path=args.file,
            company=args.company,
            vertical_code=args.vertical,
            industry=args.industry,
            skip_llm=args.skip_llm,
            selected_sections=sections_list,
        )
        print(f"\nReport generated: {report_path}")
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
