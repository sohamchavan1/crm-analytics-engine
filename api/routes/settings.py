"""
Settings endpoints.

Manages engine configuration: AI parameters, report defaults, storage.
Settings are persisted in storage/settings.json.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

SETTINGS_FILE = Path("storage/settings.json")
UPLOADS_DIR = Path("storage/uploads")
RUNS_DIR = Path("storage/runs")
FACTS_DIR = Path("storage/facts")
INSIGHTS_DIR = Path("storage/insights")
OUTPUT_DIR = Path("output")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SettingsUpdate(BaseModel):
    """Fields that can be updated via PUT."""
    l1_temperature: Optional[float] = None
    l2_temperature: Optional[float] = None
    ranking_metric: Optional[str] = None
    performers_count: Optional[int] = None
    label_separator: Optional[str] = None
    auto_cleanup_uploads: Optional[bool] = None


DEFAULT_SETTINGS = {
    "l1_temperature": 0.0,
    "l2_temperature": 0.3,
    "ranking_metric": "ctr",
    "performers_count": 5,
    "label_separator": "|",
    "auto_cleanup_uploads": True,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_settings() -> dict:
    """Load settings from disk, falling back to defaults."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # Merge with defaults (in case new keys were added)
            merged = {**DEFAULT_SETTINGS, **data}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict):
    """Persist settings to disk."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _get_dir_stats(directory: Path) -> dict:
    """Get file count and total size for a directory."""
    if not directory.exists():
        return {"file_count": 0, "size_bytes": 0}
    files = list(directory.glob("*"))
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    return {"file_count": len([f for f in files if f.is_file()]), "size_bytes": total_size}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def get_settings():
    """
    Get all engine settings including AI config, report defaults, and system info.
    """
    settings = _load_settings()

    # System info (read-only)
    aws_region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    model_id = "anthropic.claude-opus-4-6-v1"

    return {
        **settings,
        "system": {
            "aws_region": aws_region,
            "model_id": model_id,
            "engine_version": "0.1.0",
        },
    }


@router.put("")
async def update_settings(updates: SettingsUpdate):
    """
    Update engine settings. Only provided fields are updated.
    """
    settings = _load_settings()

    # Apply updates (only non-None fields)
    update_data = updates.model_dump(exclude_none=True)

    # Validate
    if "l1_temperature" in update_data:
        if not (0.0 <= update_data["l1_temperature"] <= 1.0):
            raise HTTPException(400, "l1_temperature must be between 0.0 and 1.0")
    if "l2_temperature" in update_data:
        if not (0.0 <= update_data["l2_temperature"] <= 1.0):
            raise HTTPException(400, "l2_temperature must be between 0.0 and 1.0")
    if "ranking_metric" in update_data:
        valid_metrics = ["ctr", "ctor", "conversions", "influenced_conversions"]
        if update_data["ranking_metric"] not in valid_metrics:
            raise HTTPException(400, f"ranking_metric must be one of: {valid_metrics}")
    if "performers_count" in update_data:
        if not (1 <= update_data["performers_count"] <= 20):
            raise HTTPException(400, "performers_count must be between 1 and 20")

    settings.update(update_data)
    _save_settings(settings)

    return {"status": "updated", "settings": settings}


@router.get("/storage")
async def get_storage_stats():
    """
    Get storage usage statistics.
    """
    uploads = _get_dir_stats(UPLOADS_DIR)
    runs = _get_dir_stats(RUNS_DIR)
    facts = _get_dir_stats(FACTS_DIR)
    insights = _get_dir_stats(INSIGHTS_DIR)
    output = _get_dir_stats(OUTPUT_DIR)

    total_bytes = (
        uploads["size_bytes"]
        + runs["size_bytes"]
        + facts["size_bytes"]
        + insights["size_bytes"]
        + output["size_bytes"]
    )

    return {
        "uploads": uploads,
        "runs": runs,
        "facts": facts,
        "insights": insights,
        "reports": output,
        "total_size_bytes": total_bytes,
    }


@router.delete("/uploads")
async def clear_uploads():
    """
    Delete all files in the uploads directory.
    """
    if not UPLOADS_DIR.exists():
        return {"status": "ok", "deleted_count": 0}

    count = 0
    for f in UPLOADS_DIR.glob("*"):
        if f.is_file():
            f.unlink()
            count += 1

    return {"status": "ok", "deleted_count": count}
