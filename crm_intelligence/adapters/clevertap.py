"""
CleverTap platform adapter.

Translates raw CleverTap campaign export files (CSV or Excel) into
a list of CanonicalCampaign objects that the analytics layer can consume.

This module encapsulates ALL CleverTap-specific knowledge:
- Column names and their mapping to canonical fields
- Date/time format parsing quirks
- Channel name standardization
- Platform-specific delivery rules (e.g., Push uses Viewed as Delivered proxy)

If CleverTap changes their export format, ONLY this file needs to change.
"""

import logging
from datetime import date, time, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from crm_intelligence.models.campaign import CanonicalCampaign

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column Mapping: CleverTap raw column name → canonical field name
# ---------------------------------------------------------------------------

# Primary column map (narrow 29-col format, e.g., Club Mahindra)
COLUMN_MAP = {
    "Campaign Name": "campaign_name",
    "Segments": "segment",
    "Channel": "channel",
    "estimated reach": "estimated_reach",
    "Title": "title",
    "Message": "message",
    "Start Date": "start_date",
    "Start Time": "start_time",
    "Device": "device",
    "Total Sent(users)": "sent",
    "Total Viewed(users)": "viewed",
    "Total Clicked(users)": "clicked",
    "Total Delivered(users)": "delivered",
    "Errors": "errors",
    "Click through conversions": "click_conversions",
    "Click through conversions %": "click_conversion_percent",
    "Influenced Conversions": "influenced_conversions",
    "Influenced Conversions %": "influenced_conversion_percent",
    "Labels": "labels",
}

# Alternate column names found in different CleverTap export formats
# Maps variant → canonical column name from COLUMN_MAP keys
_COLUMN_ALIASES = {
    # Wide format (121-col) with spaces before (users)
    "Total Sent (users)": "Total Sent(users)",
    "Total Viewed (users)": "Total Viewed(users)",
    "Total Clicked (users)": "Total Clicked(users)",
    "Total Delivered (users)": "Total Delivered(users)",
    # Compact format (19-col, e.g., Levis) — short names without "Total" or "(users)"
    "Sent": "Total Sent(users)",
    "Viewed": "Total Viewed(users)",
    "Clicked": "Total Clicked(users)",
    "Delivered": "Total Delivered(users)",
    # Estimated reach variants
    "Estimated Reach": "estimated reach",
    "estimated Reach": "estimated reach",
    "Estimated reach": "estimated reach",
    # Segment/Segments
    "Segment": "Segments",
    "segment": "Segments",
    # Campaign name casing
    "Campaign name": "Campaign Name",
    "campaign_name": "Campaign Name",
    # Labels variants
    "Label": "Labels",
    "labels": "Labels",
    "Tags": "Labels",
    "Category": "Labels",
    # Lowercase variants
    "start_date": "Start Date",
    "start_time": "Start Time",
    "message": "Message",
    "channel": "Channel",
    "title": "Title",
    # Mixed casing with (users)
    "Total sent(users)": "Total Sent(users)",
    "Total viewed(users)": "Total Viewed(users)",
    "Total clicked(users)": "Total Clicked(users)",
    "Total delivered(users)": "Total Delivered(users)",
    # Conversion variants
    "Click Through Conversions": "Click through conversions",
    "Click Through Conversions %": "Click through conversions %",
}

# Columns required to exist in the raw file (adapter cannot proceed without them)
# These are the absolute minimum for any meaningful analysis
REQUIRED_RAW_COLUMNS = [
    "Campaign Name",
    "Message",
    "Start Date",
    "Start Time",
    "Total Sent(users)",
    "Total Viewed(users)",
    "Total Clicked(users)",
]

# Optional columns — analysis is richer when present but not blocked without them
OPTIONAL_COLUMNS = [
    "Channel",
    "Segments",
    "Total Delivered(users)",
    "Click through conversions",
    "Influenced Conversions",
    "estimated reach",
    "Labels",
    "Title",
    "Errors",
]

# ---------------------------------------------------------------------------
# Channel Standardization
# ---------------------------------------------------------------------------

CHANNEL_MAP = {
    "WhatsApp": "WhatsApp",
    "Whatsapp": "WhatsApp",
    "whatsapp": "WhatsApp",
    "WA": "WhatsApp",
    "Push Notification": "Push Notification",
    "Push": "Push Notification",
    "PN": "Push Notification",
    "push": "Push Notification",
    "RCS": "RCS",
    "rcs": "RCS",
    "Email": "Email",
    "email": "Email",
    "SMS": "SMS",
    "sms": "SMS",
}

# ---------------------------------------------------------------------------
# Signature Detection (is this file a CleverTap export?)
# ---------------------------------------------------------------------------

# If a file contains these columns (after alias normalization), it's a CleverTap export
# Only need Campaign Name + one of the metric columns to detect
CLEVERTAP_SIGNATURE_COLUMNS = {
    "Campaign Name",
    "Total Sent(users)",
    "Total Clicked(users)",
}


def is_clevertap_export(columns: list[str]) -> bool:
    """Check if a set of column names matches a CleverTap export signature."""
    # Normalize columns using aliases first
    normalized = set(_normalize_columns(columns))
    return CLEVERTAP_SIGNATURE_COLUMNS.issubset(normalized)


def _normalize_columns(columns: list[str]) -> list[str]:
    """Map variant column names to their canonical forms."""
    result = []
    for col in columns:
        if col in _COLUMN_ALIASES:
            result.append(_COLUMN_ALIASES[col])
        else:
            result.append(col)
    return result


# ---------------------------------------------------------------------------
# Date and Time Parsing
# ---------------------------------------------------------------------------


def _parse_date(value) -> Optional[date]:
    """
    Parse a date value from CleverTap exports.

    Handles multiple formats found in real data:
    - datetime objects (from Excel parsing via openpyxl)
    - "5/7/2026" (M/D/YYYY — US format, common in CleverTap exports)
    - "07/05/2026" (DD/MM/YYYY)
    - "2026-05-07" (ISO format)
    - Excel serial numbers (e.g., 46148)
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    # Already a date or datetime object
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    # String parsing
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Try M/D/YYYY (CleverTap's most common format)
        for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        # Try pandas as last resort
        try:
            return pd.to_datetime(value).date()
        except (ValueError, TypeError):
            return None

    # Numeric (Excel serial number)
    if isinstance(value, (int, float)) and not pd.isna(value):
        try:
            # Excel serial: days since 1899-12-30
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(value))
        except (ValueError, OverflowError):
            return None

    return None


def _parse_time(value) -> Optional[time]:
    """
    Parse a time value from CleverTap exports.

    Handles:
    - time objects (already parsed)
    - datetime objects (extract time)
    - "18:30" or "18:30:00" (string)
    - 0.7708 (Excel day-fraction: 0.7708 * 24 = 18.5 → 18:30)
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    # Already a time object
    if isinstance(value, time):
        return value

    # datetime → extract time
    if isinstance(value, datetime):
        return value.time()

    # String
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    # Numeric (Excel day-fraction)
    if isinstance(value, (int, float)) and not pd.isna(value):
        try:
            total_seconds = float(value) * 24 * 3600
            hours = int(total_seconds // 3600) % 24
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            return time(hours, minutes, seconds)
        except (ValueError, OverflowError):
            return None

    return None


def _standardize_channel(raw_channel: str) -> Optional[str]:
    """Map a raw channel string to a standardized channel name."""
    if not raw_channel or (isinstance(raw_channel, float) and pd.isna(raw_channel)):
        return None
    return CHANNEL_MAP.get(str(raw_channel).strip(), None)


def _safe_int(value, default: int = 0) -> int:
    """Safely convert a value to int, handling NaN and None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Public Interface
# ---------------------------------------------------------------------------


class AdapterError:
    """One row that failed to parse, with reason and context."""

    def __init__(self, row_index: int, campaign_name: str, field: str, reason: str):
        self.row_index = row_index
        self.campaign_name = campaign_name
        self.field = field
        self.reason = reason

    def __str__(self) -> str:
        return f"Row {self.row_index} ({self.campaign_name}): {self.field} — {self.reason}"


class AdapterResult:
    """Result of adapting a file: successful campaigns + any row-level errors."""

    def __init__(
        self,
        campaigns: list[CanonicalCampaign],
        errors: list[AdapterError],
        total_rows: int,
    ):
        self.campaigns = campaigns
        self.errors = errors
        self.total_rows = total_rows

    @property
    def success_count(self) -> int:
        return len(self.campaigns)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def success_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return self.success_count / self.total_rows * 100


def _pick_sheet(filepath: Path) -> Optional[str]:
    """
    For multi-sheet XLSX files, pick the best sheet for raw campaign data.

    Priority order:
    1. Sheet named exactly "raw_data" (case-insensitive)
    2. Sheet containing "performance" (e.g., "PN_performance")
    3. Sheet containing "data" or "campaigns"
    4. First sheet (fallback)

    Returns None to use the first sheet.
    """
    try:
        xl = pd.ExcelFile(filepath)
        sheet_names = xl.sheet_names
    except Exception:
        return None

    if len(sheet_names) <= 1:
        return None

    logger.info(f"  Multi-sheet workbook detected: {sheet_names}")

    # Priority matching
    lower_map = {s.lower(): s for s in sheet_names}

    if "raw_data" in lower_map:
        return lower_map["raw_data"]

    for name_lower, name_orig in lower_map.items():
        if "performance" in name_lower:
            return name_orig

    for name_lower, name_orig in lower_map.items():
        if "data" in name_lower or "campaign" in name_lower:
            return name_orig

    return sheet_names[0]


def load_file(filepath: Path) -> pd.DataFrame:
    """
    Load a CleverTap export file (CSV or Excel) into a DataFrame.

    For multi-sheet XLSX files, automatically picks the best sheet.
    Normalizes variant column names to canonical forms.

    Raises FileNotFoundError if file doesn't exist.
    Raises ValueError if file format is unsupported or unreadable.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    suffix = filepath.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(filepath)
    elif suffix in (".xlsx", ".xls"):
        sheet = _pick_sheet(filepath)
        if sheet:
            logger.info(f"  Using sheet: '{sheet}'")
            df = pd.read_excel(filepath, sheet_name=sheet)
        else:
            df = pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Expected .csv, .xlsx, or .xls")

    if df.empty:
        raise ValueError(f"File is empty: {filepath}")

    # Normalize column names (handle variant spellings)
    df.columns = _normalize_columns(df.columns.tolist())
    logger.info(f"  Columns after normalization: {len(df.columns)} cols")

    return df


def validate_columns(df: pd.DataFrame) -> list[str]:
    """
    Check that all required CleverTap columns are present.

    Returns a list of missing column names (empty = all good).
    """
    present = set(df.columns)
    missing = [col for col in REQUIRED_RAW_COLUMNS if col not in present]
    return missing


def adapt(filepath: Path) -> AdapterResult:
    """
    Adapt a raw CleverTap export file into CanonicalCampaign objects.

    This is the main entry point for the CleverTap adapter.

    Args:
        filepath: Path to the raw CleverTap CSV or Excel export.

    Returns:
        AdapterResult containing:
        - campaigns: list of successfully parsed CanonicalCampaign objects
        - errors: list of rows that failed with reasons
        - total_rows: how many rows were in the original file

    Raises:
        FileNotFoundError: if file doesn't exist
        ValueError: if file is empty, unreadable, or missing critical columns
    """
    logger.info(f"Loading CleverTap export: {filepath}")
    df = load_file(filepath)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    # Validate required columns
    missing = validate_columns(df)
    if missing:
        raise ValueError(
            f"CleverTap export is missing required columns: {missing}\n"
            f"Available columns: {sorted(df.columns.tolist())}\n"
            f"This file may not be a CleverTap campaign export."
        )

    # Process each row
    campaigns: list[CanonicalCampaign] = []
    errors: list[AdapterError] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # +2 for 0-indexing and header row (Excel row number)
        campaign_name = str(row.get("Campaign Name", f"row_{idx}"))

        # --- Parse date ---
        parsed_date = _parse_date(row.get("Start Date"))
        if parsed_date is None:
            errors.append(AdapterError(
                row_index=row_num,
                campaign_name=campaign_name,
                field="Start Date",
                reason=f"Could not parse date value: {repr(row.get('Start Date'))}",
            ))
            continue

        # --- Parse time ---
        parsed_time = _parse_time(row.get("Start Time"))
        if parsed_time is None:
            errors.append(AdapterError(
                row_index=row_num,
                campaign_name=campaign_name,
                field="Start Time",
                reason=f"Could not parse time value: {repr(row.get('Start Time'))}",
            ))
            continue

        # --- Standardize channel ---
        has_channel_col = "Channel" in df.columns
        raw_channel = row.get("Channel", "") if has_channel_col else ""
        if not raw_channel or (isinstance(raw_channel, float) and pd.isna(raw_channel)):
            # No Channel column or empty value — infer from context
            # If file has no Channel column at all, default to Push Notification
            # (common for single-channel exports like Levis PN data)
            channel = "Push Notification"
        else:
            channel = _standardize_channel(raw_channel)
            if channel is None:
                errors.append(AdapterError(
                    row_index=row_num,
                    campaign_name=campaign_name,
                    field="Channel",
                    reason=f"Unknown channel: '{raw_channel}'. Expected one of: {list(CHANNEL_MAP.keys())}",
                ))
                continue

        # --- Get message ---
        message = row.get("Message", "")
        if not message or (isinstance(message, float) and pd.isna(message)):
            errors.append(AdapterError(
                row_index=row_num,
                campaign_name=campaign_name,
                field="Message",
                reason="Message is empty or missing. Cannot analyze creative without message text.",
            ))
            continue

        # --- Get segment ---
        segment = row.get("Segments", "")
        if not segment or (isinstance(segment, float) and pd.isna(segment)):
            segment = "Unknown"

        # --- Numeric fields (safe conversion with defaults) ---
        sent = _safe_int(row.get("Total Sent(users)"))
        if sent == 0:
            errors.append(AdapterError(
                row_index=row_num,
                campaign_name=campaign_name,
                field="Total Sent(users)",
                reason="Sent count is 0. Campaign was never sent.",
            ))
            continue

        delivered = _safe_int(row.get("Total Delivered(users)"))
        viewed = _safe_int(row.get("Total Viewed(users)"))
        clicked = _safe_int(row.get("Total Clicked(users)"))

        # Platform rule: For Push, Delivered is always 0 in CleverTap exports.
        # Use Viewed as the delivered proxy for Push Notification.
        if channel == "Push Notification" and delivered == 0 and viewed > 0:
            delivered = viewed

        # --- Parse labels (optional) ---
        labels_raw = row.get("Labels", None)
        labels_value = None
        if labels_raw is not None and not (isinstance(labels_raw, float) and pd.isna(labels_raw)):
            labels_str = str(labels_raw).strip()
            if labels_str and labels_str.lower() not in ("nan", "n/a", "none", ""):
                labels_value = labels_str

        # --- Build the canonical campaign ---
        try:
            campaign = CanonicalCampaign(
                campaign_name=campaign_name,
                channel=channel,
                segment=str(segment),
                start_date=parsed_date,
                start_time=parsed_time,
                estimated_reach=_safe_int(row.get("estimated reach")),
                sent=sent,
                delivered=delivered,
                viewed=viewed,
                clicked=clicked,
                click_conversions=_safe_int(row.get("Click through conversions")),
                influenced_conversions=_safe_int(row.get("Influenced Conversions")),
                message=str(message),
                title=row.get("Title") if not pd.isna(row.get("Title", float("nan"))) else None,
                labels=labels_value,
                errors=_safe_int(row.get("Errors")) if "Errors" in row.index else None,
                click_conversion_percent=(
                    float(row.get("Click through conversions %", 0))
                    if not pd.isna(row.get("Click through conversions %", float("nan")))
                    else None
                ),
                influenced_conversion_percent=(
                    float(row.get("Influenced Conversions %", 0))
                    if not pd.isna(row.get("Influenced Conversions %", float("nan")))
                    else None
                ),
            )
            campaigns.append(campaign)
        except Exception as e:
            errors.append(AdapterError(
                row_index=row_num,
                campaign_name=campaign_name,
                field="validation",
                reason=f"Pydantic validation failed: {e}",
            ))

    # --- Summary logging ---
    logger.info(
        f"Adaptation complete: {len(campaigns)} campaigns parsed, "
        f"{len(errors)} errors, {len(df)} total rows"
    )
    if errors:
        for err in errors[:5]:  # Log first 5 errors
            logger.warning(f"  {err}")
        if len(errors) > 5:
            logger.warning(f"  ... and {len(errors) - 5} more errors")

    return AdapterResult(campaigns=campaigns, errors=errors, total_rows=len(df))
