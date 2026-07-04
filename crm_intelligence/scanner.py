"""
Data Scanner — quick deterministic analysis of uploaded files.

Runs in <1 second. No LLM calls. Detects:
- Platform (CleverTap, MoEngage, etc.)
- Number of campaigns
- Channels present (and whether multiple)
- Whether messages/titles exist
- Whether a Labels/tags column exists
- Whether campaign names follow an extractable offer pattern
- Segment information availability
- Date range

The output (DataProfile) tells the UI which report sections are available
and provides smart defaults for the section selection screen.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DataProfile:
    """Result of scanning an input file — describes what's in the data."""

    # Basic stats
    campaign_count: int = 0
    platform: str = "unknown"  # "clevertap", "moengage", "unknown"

    # Channel info
    channels: list[str] = field(default_factory=list)
    has_multiple_channels: bool = False

    # Content availability
    has_messages: bool = False
    has_titles: bool = False
    avg_message_length_words: int = 0

    # Labels/tags
    has_labels: bool = False
    unique_labels: list[str] = field(default_factory=list)
    label_count: int = 0

    # Offer extraction
    has_offer_pattern: bool = False
    detected_pattern: Optional[str] = None
    sample_offers: list[str] = field(default_factory=list)

    # Segments
    has_segments: bool = False
    segment_count: int = 0
    segment_type: str = "unknown"  # "clean_names", "raw_queries", "none"

    # Date range
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Data capabilities (used by section registry)
    capabilities: set[str] = field(default_factory=set)

    def summary(self) -> str:
        """Human-readable summary for logging/UI."""
        lines = [
            f"Platform: {self.platform}",
            f"Campaigns: {self.campaign_count}",
            f"Channels: {', '.join(self.channels) if self.channels else 'none detected'}",
            f"Messages: {'Yes' if self.has_messages else 'No'} (avg {self.avg_message_length_words} words)",
            f"Labels: {self.label_count} unique" if self.has_labels else "Labels: None",
            f"Offer pattern: {self.detected_pattern}" if self.has_offer_pattern else "Offer pattern: None",
            f"Segments: {self.segment_count} ({self.segment_type})" if self.has_segments else "Segments: None",
        ]
        if self.date_range_start and self.date_range_end:
            lines.append(f"Date range: {self.date_range_start} to {self.date_range_end}")
        lines.append(f"Capabilities: {', '.join(sorted(self.capabilities))}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CleverTap signature columns (used to detect platform)
# ---------------------------------------------------------------------------

CLEVERTAP_SIGNATURES = {
    "Campaign Name", "Total Sent", "Total Viewed", "Total Clicked",
    "Influenced Conversions", "Type", "Labels",
}

CLEVERTAP_SIGNATURES_WIDE = {
    "Campaign Name", "Total Sent(users)", "Total Viewed(users)",
    "Total Clicked(users)", "Influenced Conversions", "Labels",
}


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------


def scan_file(file_path: str | Path) -> DataProfile:
    """
    Quick scan of an input file to determine its capabilities.

    Supports: CSV, XLSX (reads first sheet or sheet named matching common patterns).
    No LLM calls. Runs in <1 second for typical files (<500 rows).

    Args:
        file_path: Path to the input file.

    Returns:
        DataProfile describing what's in the data.
    """
    file_path = Path(file_path)
    profile = DataProfile()

    # Load data
    df = _load_data(file_path)
    if df is None or df.empty:
        logger.warning(f"Could not load data from {file_path}")
        return profile

    # Normalize column names for detection
    cols_raw = set(df.columns.tolist())
    cols_lower = {c.lower().strip(): c for c in df.columns}

    # Detect platform
    profile.platform = _detect_platform(cols_raw)
    profile.campaign_count = len(df)

    # Detect channels
    _detect_channels(df, cols_lower, profile)

    # Detect messages
    _detect_messages(df, cols_lower, profile)

    # Detect labels
    _detect_labels(df, cols_lower, profile)

    # Detect offer pattern from campaign names
    _detect_offer_pattern(df, cols_lower, profile)

    # Detect segments
    _detect_segments(df, cols_lower, profile)

    # Detect date range
    _detect_dates(df, cols_lower, profile)

    # Compute capabilities
    _compute_capabilities(profile)

    logger.info(f"Data scan complete:\n{profile.summary()}")
    return profile


# ---------------------------------------------------------------------------
# Internal detection functions
# ---------------------------------------------------------------------------


def _load_data(file_path: Path) -> Optional[pd.DataFrame]:
    """Load data from CSV or XLSX."""
    try:
        if file_path.suffix.lower() == ".csv":
            return pd.read_csv(file_path, encoding="utf-8-sig")
        elif file_path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
            # Try common sheet names for performance data
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names

            # Priority order for sheet selection
            for pattern in ["raw_data", "raw data", "performance", "data", "campaign"]:
                for name in sheet_names:
                    if pattern in name.lower():
                        df = pd.read_excel(file_path, sheet_name=name)
                        # Skip if it looks like headers aren't in row 1
                        if _has_valid_headers(df):
                            return df
                        # Try with header in row below
                        for header_row in range(1, 5):
                            df = pd.read_excel(file_path, sheet_name=name, header=header_row)
                            if _has_valid_headers(df):
                                return df

            # Fallback: first sheet
            df = pd.read_excel(file_path, sheet_name=0)
            if _has_valid_headers(df):
                return df
            # Try header offset
            for header_row in range(1, 5):
                df = pd.read_excel(file_path, sheet_name=0, header=header_row)
                if _has_valid_headers(df):
                    return df
            return pd.read_excel(file_path, sheet_name=0)
        else:
            logger.warning(f"Unsupported file format: {file_path.suffix}")
            return None
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return None


def _has_valid_headers(df: pd.DataFrame) -> bool:
    """Check if DataFrame has recognizable column headers."""
    cols = set(str(c).lower() for c in df.columns)
    # Must have at least "campaign" in some column name
    return any("campaign" in c for c in cols)


def _detect_platform(cols: set[str]) -> str:
    """Detect CRM platform from column names."""
    if CLEVERTAP_SIGNATURES.issubset(cols) or CLEVERTAP_SIGNATURES_WIDE.issubset(cols):
        return "clevertap"
    # Check for partial matches
    cols_lower = {c.lower() for c in cols}
    if any("clevertap" in c for c in cols_lower):
        return "clevertap"
    if any("moengage" in c for c in cols_lower):
        return "moengage"
    # Heuristic: CleverTap-style columns
    ct_indicators = {"total sent", "total viewed", "total clicked", "campaign name"}
    if ct_indicators.issubset(cols_lower):
        return "clevertap"
    ct_indicators_users = {"total sent(users)", "total viewed(users)", "total clicked(users)"}
    if ct_indicators_users.issubset(cols_lower):
        return "clevertap"
    return "unknown"


def _detect_channels(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect communication channels in the data."""
    # Try common channel column names
    channel_col = None
    for key in ["type", "channel", "campaign type", "communication type"]:
        if key in cols_lower:
            channel_col = cols_lower[key]
            break

    if channel_col and channel_col in df.columns:
        channels = df[channel_col].dropna().unique().tolist()
        # Standardize channel names
        standardized = set()
        for ch in channels:
            ch_str = str(ch).strip().lower()
            if "push" in ch_str:
                standardized.add("Push Notification")
            elif "whatsapp" in ch_str or "wa" == ch_str:
                standardized.add("WhatsApp")
            elif "rcs" in ch_str:
                standardized.add("RCS")
            elif "email" in ch_str:
                standardized.add("Email")
            elif "sms" in ch_str:
                standardized.add("SMS")
            elif "in-app" in ch_str or "inapp" in ch_str:
                standardized.add("In-App")
            else:
                standardized.add(str(ch).strip())

        profile.channels = sorted(standardized)
        profile.has_multiple_channels = len(standardized) > 1
    else:
        # Try to infer from campaign names
        names = _get_campaign_names(df, cols_lower)
        if names:
            inferred = set()
            for name in names:
                name_upper = name.upper()
                if "_PN_" in name_upper or name_upper.startswith("PUSH_"):
                    inferred.add("Push Notification")
                elif "_WA_" in name_upper or "_WHATSAPP_" in name_upper:
                    inferred.add("WhatsApp")
                elif "_RCS_" in name_upper:
                    inferred.add("RCS")
                elif "_EMAIL_" in name_upper:
                    inferred.add("Email")
                elif "_SMS_" in name_upper:
                    inferred.add("SMS")
            if inferred:
                profile.channels = sorted(inferred)
                profile.has_multiple_channels = len(inferred) > 1
            else:
                # All same, probably Push from naming like Push_XXX
                if names and all(n.lower().startswith("push_") for n in names[:10]):
                    profile.channels = ["Push Notification"]
                    profile.has_multiple_channels = False


def _detect_messages(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect whether message text exists."""
    msg_col = None
    for key in ["message", "message text", "body", "content", "message body"]:
        if key in cols_lower:
            msg_col = cols_lower[key]
            break

    if msg_col and msg_col in df.columns:
        messages = df[msg_col].dropna()
        if len(messages) > 0:
            profile.has_messages = True
            # Average word count
            word_counts = messages.astype(str).str.split().str.len()
            profile.avg_message_length_words = int(word_counts.mean())

    # Check titles
    title_col = None
    for key in ["title", "subject", "heading", "header"]:
        if key in cols_lower:
            title_col = cols_lower[key]
            break

    if title_col and title_col in df.columns:
        titles = df[title_col].dropna()
        profile.has_titles = len(titles) > 0


def _detect_labels(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect labels/tags column."""
    label_col = None
    for key in ["labels", "tags", "category", "categories", "campaign tags"]:
        if key in cols_lower:
            label_col = cols_lower[key]
            break

    if label_col and label_col in df.columns:
        labels_series = df[label_col].dropna()
        if len(labels_series) > 0:
            profile.has_labels = True
            # Parse unique labels (handle pipe-separated)
            all_labels = set()
            for val in labels_series:
                val_str = str(val).strip()
                if "|" in val_str:
                    for part in val_str.split("|"):
                        part = part.strip()
                        if part and part.lower() not in ("n/a", "nan", "none"):
                            all_labels.add(part)
                elif val_str.lower() not in ("n/a", "nan", "none", ""):
                    all_labels.add(val_str)

            profile.unique_labels = sorted(all_labels)[:50]
            profile.label_count = len(all_labels)


def _detect_offer_pattern(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect if campaign names follow a pattern with extractable offers."""
    names = _get_campaign_names(df, cols_lower)
    if not names or len(names) < 5:
        return

    # Pattern 1: PROGRAM_CHANNEL_OFFER_DATE (Club Mahindra style)
    # e.g., HFRP_PN_Anniversary_09052026
    pattern_program_channel_offer = re.compile(
        r"^[A-Z]+_[A-Z]{2,3}_([A-Za-z0-9]+)_\d{6,8}$"
    )
    matches = sum(1 for n in names if pattern_program_channel_offer.match(n))
    if matches > len(names) * 0.5:
        profile.has_offer_pattern = True
        profile.detected_pattern = "PROGRAM_CHANNEL_OFFER_DATE"
        # Extract sample offers
        offers = set()
        for n in names:
            m = pattern_program_channel_offer.match(n)
            if m:
                offers.add(m.group(1))
        profile.sample_offers = sorted(offers)[:10]
        return

    # Pattern 2: Push_THEME_TIME_DATE (Levis style) — NOT an offer pattern
    # e.g., Push_EOSSLiveNow_21PM_14062026
    # This has themes but they're not clean "offers" — better handled by labels


def _detect_segments(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect segment/audience information."""
    seg_col = None
    for key in ["segment", "audience", "user segment", "who query", "segment name"]:
        if key in cols_lower:
            seg_col = cols_lower[key]
            break

    if seg_col and seg_col in df.columns:
        segments = df[seg_col].dropna().unique()
        if len(segments) > 0:
            profile.has_segments = True
            profile.segment_count = len(segments)

            # Determine if segments are clean names or raw queries
            sample = str(segments[0])
            if len(sample) > 80 or "(" in sample:
                profile.segment_type = "raw_queries"
            else:
                profile.segment_type = "clean_names"


def _detect_dates(df: pd.DataFrame, cols_lower: dict, profile: DataProfile) -> None:
    """Detect date range from the data."""
    date_col = None
    for key in ["start date", "campaign start date", "run date", "date", "sent date"]:
        if key in cols_lower:
            date_col = cols_lower[key]
            break

    if date_col and date_col in df.columns:
        try:
            dates = pd.to_datetime(df[date_col], errors="coerce", dayfirst=False)
            dates = dates.dropna()
            if len(dates) > 0:
                profile.date_range_start = dates.min().date()
                profile.date_range_end = dates.max().date()
        except Exception:
            pass


def _get_campaign_names(df: pd.DataFrame, cols_lower: dict) -> list[str]:
    """Extract campaign names from the DataFrame."""
    name_col = None
    for key in ["campaign name", "campaign_name", "name"]:
        if key in cols_lower:
            name_col = cols_lower[key]
            break

    if name_col and name_col in df.columns:
        return df[name_col].dropna().astype(str).tolist()
    return []


def _compute_capabilities(profile: DataProfile) -> None:
    """Compute the set of data capabilities from detected features."""
    caps = set()

    # Always have basic campaigns
    if profile.campaign_count > 0:
        caps.add("campaigns")

    if profile.has_multiple_channels:
        caps.add("multiple_channels")

    if profile.has_messages:
        caps.add("messages")

    if profile.has_labels:
        caps.add("labels")

    if profile.has_offer_pattern:
        caps.add("offer_extraction")

    if profile.has_segments:
        caps.add("segments")

    profile.capabilities = caps
