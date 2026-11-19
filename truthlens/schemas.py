"""Pydantic v2 data models for TruthLens.

The models directly reflect the contracts described in SPEC.md section 5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Location model – captures where a finding applies.
# ---------------------------------------------------------------------------
class Location(BaseModel):
    type: Literal["region", "frame", "timestamp", "metadata", "text_span", "file"]
    bbox: Optional[List[int]] = None  # [x, y, w, h] for region/frame
    frame_index: Optional[int] = None
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    detail: Optional[str] = None

    @model_validator(mode="after")
    def _check_bbox_length(self) -> Location:
        if self.bbox is not None and len(self.bbox) != 4:
            raise ValueError("bbox must contain exactly four integers")
        return self


# ---------------------------------------------------------------------------
# Finding model – core output of every analyzer.
# ---------------------------------------------------------------------------
class Finding(BaseModel):
    id: str
    modality: Literal["image", "video", "audio", "text", "cross_modal", "unknown"]
    analyzer: str
    indicator: str
    status: Literal["flagged", "clear", "unavailable"]
    confidence: Literal["low", "medium", "high"]
    raw_score: Optional[float] = None
    location: Location
    explanation: str
    limitations: str
    evidence_refs: List[str]
    source_file_sha256: str

    @field_validator("explanation", "limitations")
    @classmethod
    def _check_not_empty_or_whitespace(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Must not be empty or whitespace-only")
        return v

    @model_validator(mode="after")
    def _check_raw_score_range(self) -> Finding:
        if self.raw_score is not None and not (0.0 <= self.raw_score <= 1.0):
            raise ValueError("raw_score must be between 0 and 1")
        return self


# ---------------------------------------------------------------------------
# InputFile model – information about each uploaded artifact.
# ---------------------------------------------------------------------------
class InputFile(BaseModel):
    file_id: str
    filename: str
    media_type: Literal["image", "video", "audio", "text", "unknown"]
    sha256: str
    size_bytes: int


# ---------------------------------------------------------------------------
# Overall assessment model – part of the final report.
# ---------------------------------------------------------------------------
class Overall(BaseModel):
    level: Literal["low", "medium", "high", "inconclusive"]
    summary: str
    reasoning: str
    supporting_findings: List[str]
    caveats: List[str]


# ---------------------------------------------------------------------------
# Analysis log entry – records each step of the pipeline.
# ---------------------------------------------------------------------------
class LogEntry(BaseModel):
    time: str  # ISO‑8601 timestamp
    step: str
    file: str
    result: Literal["ok", "unavailable"]
    note: str


# ---------------------------------------------------------------------------
# Full report model – what the UI ultimately returns.
# ---------------------------------------------------------------------------
class Report(BaseModel):
    case_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    inputs: List[InputFile]
    context: dict = Field(default_factory=dict)
    findings: List[Finding]
    overall: Overall
    recommended_human_checks: List[str]
    analysis_log: List[LogEntry]
