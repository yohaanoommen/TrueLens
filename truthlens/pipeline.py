"""Pipeline orchestration for TruthLens.

The ``run_case`` function receives a list of uploaded file paths and an optional
context dictionary (e.g. a caption). It stores the originals, runs real analyzers
for supported modalities (image), and stub findings for other modalities.
Writes the JSON representation to ``data/cases/<case_id>/report.json``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping

from .analyzers import image as image_analyzer
from .schemas import Finding, InputFile, LogEntry, Overall, Report
from .storage import DATA_ROOT, detect_media_type, save_originals
from .stubs import make_stub_findings


def _build_overall(findings: List[Finding]) -> Overall:
    """Create a minimal ``Overall`` assessment."""
    flagged = [f.id for f in findings if f.status == "flagged"]
    has_unavailable = any(f.status == "unavailable" for f in findings)
    has_stubs = any(f.analyzer.startswith("STUB.") for f in findings)

    if findings and all(f.status == "unavailable" for f in findings):
        level = "inconclusive"
        summary = "Analysis unavailable for all uploaded files."
        reasoning = "All inputs have unsupported formats or could not be processed."
    elif flagged:
        high_conf = any(
            f.confidence == "high" for f in findings if f.status == "flagged"
        )
        med_conf = [
            f
            for f in findings
            if f.status == "flagged" and f.confidence == "medium"
        ]
        if high_conf or len(med_conf) >= 2:
            level = "medium"
        else:
            level = "low"
        summary = f"{len(flagged)} indicator(s) flagged during analysis."
        reasoning = "Flagged indicators warrant human review and correlation with source context."
    else:
        level = "low"
        summary = "No anomalous indicators flagged."
        reasoning = "Analyzers completed with clear results."

    caveats = []
    if has_stubs:
        caveats.append("Some modalities used stub analyzers.")
    if has_unavailable:
        caveats.append("One or more files or analyzer steps were unavailable.")
    if not caveats:
        caveats.append(
            "Automated forensic signals only; human verification required."
        )

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
                note=(
                    f.limitations
                    if f.status == "unavailable"
                    else f"{f.status}: {f.indicator}"
                ),
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
    case_dir = DATA_ROOT / case_id

    findings: List[Finding] = []
    for inp in inputs:
        if inp.media_type == "image":
            orig_file_path = case_dir / "originals" / inp.filename
            img_findings = image_analyzer.analyze(
                str(orig_file_path), str(case_dir), dict(context)
            )
            findings.extend(img_findings)
        else:
            # Keep stub findings for other media types (video, audio, text, unknown)
            stub_list = make_stub_findings([inp])
            findings.extend(stub_list)

    overall = _build_overall(findings)
    analysis_log = _build_log(findings)

    report = Report(
        case_id=case_id,
        inputs=inputs,
        context=dict(context),
        findings=findings,
        overall=overall,
        recommended_human_checks=[
            "Verify the original source and chain of custody.",
            "Cross-reference findings across available modalities.",
        ],
        analysis_log=analysis_log,
    )

    # Persist the JSON report.
    report_path = case_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2))
    return report
