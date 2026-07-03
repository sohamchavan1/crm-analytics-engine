"""
Adapter registry — auto-detects the platform and routes to the correct adapter.

Usage:
    from crm_intelligence.adapters.registry import detect_platform, get_adapter

    platform = detect_platform(df.columns.tolist())
    result = get_adapter(platform).adapt(filepath)

Adding a new platform:
    1. Create a new adapter module (e.g., adapters/moengage.py)
    2. Implement the same interface: adapt(filepath) → AdapterResult
    3. Add signature detection to this registry
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from crm_intelligence.adapters import clevertap

logger = logging.getLogger(__name__)


# Supported platforms
PLATFORMS = {
    "clevertap": {
        "name": "CleverTap",
        "detect": clevertap.is_clevertap_export,
        "adapt": clevertap.adapt,
    },
    # Future: "moengage": { "name": "MoEngage", "detect": ..., "adapt": ... }
}


def detect_platform(columns: list[str]) -> Optional[str]:
    """
    Auto-detect which CRM platform produced this file based on column names.

    Returns the platform key (e.g., "clevertap") or None if unrecognized.
    """
    for platform_key, config in PLATFORMS.items():
        if config["detect"](columns):
            logger.info(f"Platform detected: {config['name']}")
            return platform_key

    logger.warning(f"Could not detect platform from columns: {columns[:10]}...")
    return None


def adapt_file(filepath: Path, platform: Optional[str] = None) -> clevertap.AdapterResult:
    """
    Adapt a raw CRM export file into CanonicalCampaign objects.

    If platform is not specified, attempts auto-detection from column names.

    Args:
        filepath: Path to the raw export file (CSV or Excel).
        platform: Platform key ("clevertap", "moengage") or None for auto-detect.

    Returns:
        AdapterResult with campaigns and any row-level errors.

    Raises:
        ValueError: if platform cannot be detected or is unsupported.
        FileNotFoundError: if file doesn't exist.
    """
    filepath = Path(filepath)

    # Auto-detect platform if not specified
    if platform is None:
        df = clevertap.load_file(filepath)
        platform = detect_platform(df.columns.tolist())
        if platform is None:
            raise ValueError(
                f"Could not auto-detect CRM platform from file: {filepath.name}\n"
                f"Columns found: {df.columns.tolist()[:10]}...\n"
                f"Supported platforms: {[v['name'] for v in PLATFORMS.values()]}\n"
                f"Please specify the platform explicitly."
            )

    # Get the adapter
    if platform not in PLATFORMS:
        raise ValueError(
            f"Unsupported platform: '{platform}'. "
            f"Supported: {list(PLATFORMS.keys())}"
        )

    adapter_fn = PLATFORMS[platform]["adapt"]
    return adapter_fn(filepath)
