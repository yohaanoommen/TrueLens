"""Pipeline orchestration for TruthLens.

The ``run_case`` function receives a list of uploaded file paths and an optional
context dictionary (e.g. a caption). It stores the originals, runs real analyzers
for supported modalities (image), and stub findings for other modalities.
Computes overall confidence via truthlens.confidence, writes report.json, and
renders the self-contained HTML report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping

from .analyzers import image as image_analyzer
from .confidence import compute_overall, generate_recommended_checks
from .report.generator import save_html_report
from .schemas import Finding, InputFile, LogEntry, Overall, Report
from .storage import DATA_ROOT, detect_media_type, save_originals
from .stubs import make_stub_findings


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

    # Compute overall confidence and dynamic human checks using confidence rules
    overall = compute_overall(findings)
    recommended_checks = generate_recommended_checks(findings)
    analysis_log = _build_log(findings)

    report = Report(
        case_id=case_id,
        inputs=inputs,
        context=dict(context),
        findings=findings,
        overall=overall,
        recommended_human_checks=recommended_checks,
        analysis_log=analysis_log,
    )

    # Persist the JSON report.
    report_path = case_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    # Persist the self-contained HTML report.
    save_html_report(report, case_dir)

    return report
