"""
Report generation endpoints.

Handles:
1. File upload + instant data scan (returns capabilities for section picker)
2. Full report generation with Server-Sent Events (SSE) progress streaming
"""

import asyncio
import json
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from crm_intelligence.adapters.clevertap import load_file, is_clevertap_export
from crm_intelligence.scanner import scan_file
from crm_intelligence.sections import (
    ALL_SECTION_IDS,
    get_available_sections,
    get_default_sections,
    get_required_l1_dimensions,
    needs_l1,
    needs_l2,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Temp storage for uploaded files (keyed by upload_id)
UPLOAD_DIR = Path("storage/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1: File Upload + Scan
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_and_scan(file: UploadFile = File(...)):
    """
    Upload a CRM export file and scan it for capabilities.

    Returns:
    - upload_id: reference for subsequent generate call
    - platform: detected CRM platform
    - data_profile: campaign count, channels, capabilities, etc.
    - available_sections: sections that can be generated from this data
    - default_sections: suggested pre-checked sections
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Expected .csv, .xlsx, or .xls",
        )

    # Save uploaded file
    upload_id = str(uuid.uuid4())[:8]
    upload_path = UPLOAD_DIR / f"{upload_id}{suffix}"

    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"File uploaded: {file.filename} → {upload_path} ({len(content)} bytes)")

    # Scan the file
    try:
        profile = scan_file(upload_path)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"File scan failed: {str(e)}")

    # Get available sections based on scan
    available = get_available_sections(profile.capabilities)
    defaults = get_default_sections("all", profile.capabilities)

    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "platform": profile.platform,
        "data_profile": {
            "campaign_count": profile.campaign_count,
            "channels": profile.channels,
            "has_messages": profile.has_messages,
            "has_labels": profile.has_labels,
            "unique_labels": profile.unique_labels[:20],  # Top 20
            "has_offer_pattern": profile.has_offer_pattern,
            "capabilities": sorted(profile.capabilities),
        },
        "available_sections": [
            {"id": s.id, "name": s.name, "description": s.description}
            for s in available
        ],
        "default_sections": defaults,
    }


# ---------------------------------------------------------------------------
# Step 2: Generate Report (SSE streaming)
# ---------------------------------------------------------------------------


@router.post("/run")
async def generate_report(
    upload_id: str = Form(...),
    company: str = Form(...),
    vertical_code: str = Form(...),
    sections: str = Form(""),  # Comma-separated section IDs
):
    """
    Generate a CRM Intelligence Report with progress streaming via SSE.

    The response is a stream of Server-Sent Events (SSE) showing pipeline progress.
    Final event contains the report metadata (run_id, download path).
    """
    # Validate upload exists
    upload_path = _find_upload(upload_id)
    if upload_path is None:
        raise HTTPException(status_code=404, detail=f"Upload not found: {upload_id}")

    # Parse sections
    selected_sections = None
    if sections.strip():
        selected_sections = [s.strip() for s in sections.split(",") if s.strip()]
        invalid = [s for s in selected_sections if s not in ALL_SECTION_IDS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section IDs: {invalid}. Valid: {ALL_SECTION_IDS}",
            )

    # Return SSE stream
    return StreamingResponse(
        _pipeline_stream(upload_path, company, vertical_code, selected_sections),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _find_upload(upload_id: str) -> Optional[Path]:
    """Find an uploaded file by its ID."""
    for ext in (".csv", ".xlsx", ".xls"):
        path = UPLOAD_DIR / f"{upload_id}{ext}"
        if path.exists():
            return path
    return None


def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _pipeline_stream(
    file_path: Path,
    company: str,
    vertical_code: str,
    selected_sections: Optional[list[str]],
):
    """
    Run the pipeline and yield SSE events for each stage in real time.

    Uses an asyncio.Queue bridged from the pipeline thread via call_soon_threadsafe.
    The async generator awaits the queue, so events flush to the client immediately.

    Key buffering mitigation:
    - An initial 2KB comment flushes browser-level read buffers (Chrome/Edge hold
      the first few KB before surfacing data to ReadableStream).
    - asyncio.sleep(0) after each yield ensures the event loop processes the send.
    """
    import concurrent.futures

    # --- Flush browser buffer ---
    # Browsers (esp. Chrome) buffer ~2-4KB before delivering to ReadableStream.read().
    # SSE comments (lines starting with ":") are ignored by clients but push bytes.
    yield ": " + " " * 2048 + "\n\n"
    await asyncio.sleep(0)

    # Send an initial "connected" event so the frontend knows the stream is live
    yield _sse_event("step", {"step": 0, "total": 8, "message": "Connected — starting pipeline...", "detail": None, "status": "running"})
    await asyncio.sleep(0)

    loop = asyncio.get_running_loop()
    # asyncio.Queue — awaitable from the async generator
    progress_q: asyncio.Queue = asyncio.Queue()

    # Sentinel to signal pipeline completion
    _DONE = object()
    _ERROR = object()

    def _progress_callback(step: int, total: int, message: str, detail: str = None):
        """Called from the pipeline thread — bridges to the async queue."""
        loop.call_soon_threadsafe(
            progress_q.put_nowait,
            {"step": step, "total": total, "message": message, "detail": detail, "status": "running"},
        )

    def _run_blocking():
        """Run the full pipeline in a thread with progress reporting."""
        try:
            from crm_intelligence.main import run_pipeline
            result = run_pipeline(
                file_path=file_path,
                company=company,
                vertical_code=vertical_code,
                selected_sections=selected_sections,
                progress_callback=_progress_callback,
            )
            loop.call_soon_threadsafe(progress_q.put_nowait, (_DONE, result))
        except Exception as exc:
            loop.call_soon_threadsafe(progress_q.put_nowait, (_ERROR, exc))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(_run_blocking)

    try:
        while True:
            # Await next event from the queue (blocks until something arrives)
            event = await progress_q.get()

            # Check for completion sentinel
            if isinstance(event, tuple) and len(event) == 2:
                sentinel, payload = event
                if sentinel is _DONE:
                    # Pipeline succeeded — send final events
                    report_path = payload

                    # Extract run_id
                    run_id = None
                    try:
                        runs_dir = Path("storage/runs")
                        if runs_dir.exists():
                            run_files = sorted(runs_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
                            if run_files:
                                run_id = run_files[0].stem
                    except Exception:
                        pass

                    yield _sse_event("step", {"step": 8, "total": 8, "message": "Complete!", "detail": None, "status": "complete"})
                    await asyncio.sleep(0)
                    yield _sse_event("complete", {
                        "report_path": str(report_path),
                        "run_id": run_id,
                        "message": "Report generated successfully",
                    })
                    break

                elif sentinel is _ERROR:
                    # Pipeline failed
                    logger.error(f"Pipeline failed: {payload}", exc_info=True)
                    yield _sse_event("error", {"message": str(payload)})
                    break
            else:
                # Regular progress event — yield immediately
                yield _sse_event("step", event)
                await asyncio.sleep(0)

    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        yield _sse_event("error", {"message": str(e)})

    # Cleanup: remove the upload file now that pipeline is done
    try:
        if file_path.exists() and file_path.resolve().parent == UPLOAD_DIR.resolve():
            file_path.unlink(missing_ok=True)
            logger.info(f"Cleaned up upload file: {file_path.name}")
    except Exception:
        pass

    executor.shutdown(wait=False)
