"""
Run model — tracks the state and artifacts of each analysis execution.

A Run is created when the user submits a file for analysis.
It progresses through states: pending → running → complete (or failed).
Each completed run stores references to its artifacts (facts, report).
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Analysis run lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Run(BaseModel):
    """
    One analysis execution.

    Tracks what was analyzed, when, and what was produced.
    Enables historical comparison (load prior run's facts for trend analysis).
    """

    # --- Identity ---
    run_id: str = Field(description="Unique identifier (generated at creation)")
    company: str = Field(description="Company name this run belongs to")
    vertical_code: str = Field(description="Which vertical was analyzed")

    # --- Source ---
    source_platform: str = Field(description="'clevertap' or 'moengage'")
    source_filename: str = Field(description="Original uploaded filename")
    campaign_count: int = Field(default=0, description="Number of campaigns in the dataset")
    channels: list[str] = Field(default_factory=list, description="Channels present in the data")
    date_range_start: Optional[str] = Field(default=None, description="Earliest campaign date")
    date_range_end: Optional[str] = Field(default=None, description="Latest campaign date")

    # --- State ---
    status: RunStatus = Field(default=RunStatus.PENDING)
    error_message: Optional[str] = Field(default=None, description="Why it failed (if status=failed)")

    # --- Artifact paths (relative to output directory) ---
    facts_path: Optional[str] = Field(default=None, description="Path to facts.json")
    report_path: Optional[str] = Field(default=None, description="Path to report.docx")
    insights_path: Optional[str] = Field(default=None, description="Path to insights.json")

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
