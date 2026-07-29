"""
Reports listing and download endpoints.

Serves the generated reports history with metadata,
and provides DOCX file downloads.

Storage layout:
  storage/runs/{run_id}.json      — Run metadata
  storage/facts/{run_id}_facts.json   — Computed facts
  storage/insights/{run_id}_insights.json — LLM insights
  output/                         — Generated DOCX reports
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter()

RUNS_DIR = Path("storage/runs")
FACTS_DIR = Path("storage/facts")
INSIGHTS_DIR = Path("storage/insights")
OUTPUT_DIR = Path("output")


def _load_runs(
    company: Optional[str] = None,
    vertical: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Load run metadata from storage, optionally filtered."""
    if not RUNS_DIR.exists():
        return []

    runs = []
    for run_file in sorted(RUNS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))

            # Apply filters
            if company and data.get("company", "").lower() != company.lower():
                continue
            if vertical and data.get("vertical_code", "").lower() != vertical.lower():
                continue

            runs.append(data)

            if len(runs) >= limit:
                break
        except Exception:
            continue

    return runs


@router.get("")
async def list_reports(
    company: Optional[str] = Query(None, description="Filter by company name"),
    vertical: Optional[str] = Query(None, description="Filter by vertical code"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List all generated reports with metadata.

    Supports filtering by company and vertical.
    Returns most recent first.
    """
    runs = _load_runs(company=company, vertical=vertical, limit=limit)

    reports = []
    for run in runs:
        reports.append({
            "run_id": run.get("run_id"),
            "company": run.get("company"),
            "vertical_code": run.get("vertical_code"),
            "status": run.get("status"),
            "source_platform": run.get("source_platform"),
            "source_filename": run.get("source_filename"),
            "campaign_count": run.get("campaign_count"),
            "channels": run.get("channels", []),
            "date_range_start": run.get("date_range_start"),
            "date_range_end": run.get("date_range_end"),
            "report_path": run.get("report_path"),
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
        })

    return {"reports": reports, "total": len(reports)}


@router.get("/{run_id}")
async def get_report(run_id: str):
    """Get detailed metadata for a specific report run."""
    run_file = RUNS_DIR / f"{run_id}.json"

    if not run_file.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {run_id}")

    data = json.loads(run_file.read_text(encoding="utf-8"))

    # Load facts summary if available
    facts_file = FACTS_DIR / f"{run_id}_facts.json"
    facts_summary = None
    if facts_file.exists():
        try:
            facts = json.loads(facts_file.read_text(encoding="utf-8"))
            overall = facts.get("overall", {})
            facts_summary = {
                "total_campaigns": overall.get("total_campaigns"),
                "total_sent": overall.get("total_sent"),
                "overall_ctr": overall.get("overall_ctr"),
                "overall_ctor": overall.get("overall_ctor"),
                "total_influenced_conversions": overall.get("total_influenced_conversions"),
            }
        except Exception:
            pass

    # Load insights summary if available
    insights_file = INSIGHTS_DIR / f"{run_id}_insights.json"
    insights_summary = None
    if insights_file.exists():
        try:
            insights = json.loads(insights_file.read_text(encoding="utf-8"))
            insights_summary = {
                "executive_summary": insights.get("executive_summary"),
                "recommendations": insights.get("recommendations", [])[:3],
            }
        except Exception:
            pass

    return {
        "run": data,
        "facts_summary": facts_summary,
        "insights_summary": insights_summary,
    }


@router.get("/{run_id}/download")
async def download_report(run_id: str):
    """Download the generated DOCX report for a run."""
    run_file = RUNS_DIR / f"{run_id}.json"

    if not run_file.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {run_id}")

    data = json.loads(run_file.read_text(encoding="utf-8"))
    report_path = data.get("report_path")

    if not report_path:
        raise HTTPException(status_code=404, detail="No report file for this run")

    report_file = Path(report_path)
    if not report_file.exists():
        # Try relative to output dir
        report_file = OUTPUT_DIR / report_file.name
        if not report_file.exists():
            # Try searching output dir for any file containing the run_id
            for f in OUTPUT_DIR.glob(f"*{run_id}*"):
                report_file = f
                break
            else:
                raise HTTPException(status_code=404, detail="Report file not found on disk")

    return FileResponse(
        path=str(report_file),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=report_file.name,
    )


@router.delete("/{run_id}")
async def delete_report(run_id: str):
    """Delete a report and all its associated artifacts (run, facts, insights, DOCX)."""
    run_file = RUNS_DIR / f"{run_id}.json"

    if not run_file.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {run_id}")

    # Load run data to find report file path
    try:
        data = json.loads(run_file.read_text(encoding="utf-8"))
        report_path = data.get("report_path")
    except Exception:
        report_path = None

    # Delete all associated files
    run_file.unlink(missing_ok=True)

    facts_file = FACTS_DIR / f"{run_id}_facts.json"
    facts_file.unlink(missing_ok=True)

    insights_file = INSIGHTS_DIR / f"{run_id}_insights.json"
    insights_file.unlink(missing_ok=True)

    # Delete the DOCX report file
    if report_path:
        report_file = Path(report_path)
        if report_file.exists():
            report_file.unlink(missing_ok=True)
        else:
            # Try in output dir
            alt = OUTPUT_DIR / report_file.name
            alt.unlink(missing_ok=True)

    return {"status": "deleted", "run_id": run_id}


@router.get("/{run_id}/facts")
async def get_facts(run_id: str):
    """Get the complete computed facts for a run (for in-app intelligence view)."""
    facts_file = FACTS_DIR / f"{run_id}_facts.json"

    if not facts_file.exists():
        raise HTTPException(status_code=404, detail=f"Facts not found for run: {run_id}")

    return json.loads(facts_file.read_text(encoding="utf-8"))


@router.get("/{run_id}/insights")
async def get_insights(run_id: str):
    """Get the LLM-generated insights for a run."""
    insights_file = INSIGHTS_DIR / f"{run_id}_insights.json"

    if not insights_file.exists():
        raise HTTPException(status_code=404, detail=f"Insights not found for run: {run_id}")

    return json.loads(insights_file.read_text(encoding="utf-8"))
