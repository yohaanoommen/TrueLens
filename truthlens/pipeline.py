"""Pipeline orchestration for Stage 1.

The ``run_case`` function receives a list of uploaded file paths and an optional
context dictionary (e.g. a caption). It stores the originals, creates a stub
report using the placeholder findings from ``stubs.py`` and returns a ``Report``
model instance. The function also writes the JSON representation of the report
to ``data/cases/<case_id>/report.json`` so the UI can offer a download.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping

from .schemas import Finding, InputFile, LogEntry, Overall, Report
from .storage import detect_media_type, save_originals
from .stubs import make_stub_findings


def _build_overall(findings: List[Finding]) -> Overall:
    """Create a minimal ``Overall`` assessment."""
    flagged = [f.id for f in findings if f.status == "flagged"]
    has_unavailable = any(f.status == "unavailable" for f in findings)

    if findings and all(f.status == "unavailable" for f in findings):
        level = "inconclusive"
        summary = "Analysis unavailable for all uploaded files."
        reasoning = "All inputs have unsupported formats or could not be processed."
    else:
        level = "low"
        summary = "Stub analysis – no real detection performed."
        reasoning = "Findings are placeholders generated for UI development."

    caveats = ["The current pipeline contains only stub findings."]
    if has_unavailable:
        caveats.append("One or more files had unsupported formats.")

    return Overall(
        level=level,
        summary=summary,
        reasoning=reasoning,
        supporting_findings=flagged,
        caveats=caveats,
    )


def _build_log(findings: List[Finding]) -> List[LogEntry]:
    now_iso = datetime.now(timezone.utc).isoformat()
    log: List[LogEntry] = []
    for f in findings:
        log.append(
            LogEntry(
                time=now_iso,
                step=f.analyzer,
                file=f.source_file_sha256,
                result="unavailable" if f.status == "unavailable" else "ok",
                note=f.limitations if f.status == "unavailable" else "stub finding",
            )
        )
    return log


def run_case(file_paths: List[Path], context: Mapping | None = None) -> Report:
    """Execute a full analysis case.

    Parameters
    ----------
    file_paths:
        Absolute ``Path`` objects pointing at the uploaded files.
    context:
        Optional dictionary with additional user‑provided information (e.g.
        ``{"caption": "…"}``).
    """
    if context is None:
        context = {}

    # Store originals and obtain InputFile metadata.
    case_id, inputs = save_originals(file_paths)

    # Generate stub findings per stored file.
    findings = make_stub_findings(inputs)

    overall = _build_overall(findings)
    analysis_log = _build_log(findings)

    report = Report(
        case_id=case_id,
        inputs=inputs,
        context=dict(context),
        findings=findings,
        overall=overall,
        recommended_human_checks=["Verify file authenticity manually."],
        analysis_log=analysis_log,
    )

    # Persist the JSON report.
    report_path = (
        Path(__file__).resolve().parent.parent / "data" / "cases" / case_id / "report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2))
    return report
