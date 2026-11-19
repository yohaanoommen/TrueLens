"""Tests for TruthLens schemas, validation, stubs, and pipeline.

Validates:
(a) Empty or whitespace-only limitations and explanations are rejected.
(b) Stub findings carry the real sha256 and matching modality.
(c) Unknown file extensions produce an 'unavailable' finding with the reason.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from pydantic import ValidationError

from truthlens.pipeline import run_case
from truthlens.schemas import Finding, InputFile, Location, LogEntry, Overall, Report
from truthlens.storage import sha256_file
from truthlens.stubs import make_stub_findings


def _make_dummy_location() -> Location:
    return Location(type="file")


# ---------------------------------------------------------------------------
# (a) Empty or whitespace-only limitations and explanations are rejected
# ---------------------------------------------------------------------------
def test_empty_limitations_rejected():
    with pytest.raises(ValidationError):
        Finding(
            id="f_0001",
            modality="image",
            analyzer="STUB.image",
            indicator="Test indicator",
            status="flagged",
            confidence="low",
            location=_make_dummy_location(),
            explanation="Valid explanation.",
            limitations="",  # empty
            evidence_refs=[],
            source_file_sha256="abc123def456",
        )


def test_whitespace_only_limitations_rejected():
    with pytest.raises(ValidationError):
        Finding(
            id="f_0001",
            modality="image",
            analyzer="STUB.image",
            indicator="Test indicator",
            status="flagged",
            confidence="low",
            location=_make_dummy_location(),
            explanation="Valid explanation.",
            limitations="   \t\n  ",  # whitespace only
            evidence_refs=[],
            source_file_sha256="abc123def456",
        )


def test_empty_explanation_rejected():
    with pytest.raises(ValidationError):
        Finding(
            id="f_0001",
            modality="image",
            analyzer="STUB.image",
            indicator="Test indicator",
            status="flagged",
            confidence="low",
            location=_make_dummy_location(),
            explanation="",  # empty
            limitations="Valid limitation.",
            evidence_refs=[],
            source_file_sha256="abc123def456",
        )


def test_valid_finding_accepted():
    finding = Finding(
        id="f_0001",
        modality="image",
        analyzer="STUB.image",
        indicator="Test indicator",
        status="flagged",
        confidence="low",
        location=_make_dummy_location(),
        explanation="Valid explanation.",
        limitations="Valid limitation.",
        evidence_refs=[],
        source_file_sha256="abc123def456",
    )
    assert finding.limitations == "Valid limitation."
    assert finding.explanation == "Valid explanation."


# ---------------------------------------------------------------------------
# (b) Stub findings carry real sha256 and matching modality
# ---------------------------------------------------------------------------
def test_stub_findings_real_sha256_and_modality():
    inputs = [
        InputFile(
            file_id="f_0001",
            filename="photo.jpg",
            media_type="image",
            sha256="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            size_bytes=1024,
        ),
        InputFile(
            file_id="f_0002",
            filename="speech.wav",
            media_type="audio",
            sha256="222233334444555566667777888899990000aaaabbbbccccddddeeeeffff1111",
            size_bytes=2048,
        ),
        InputFile(
            file_id="f_0003",
            filename="clip.mp4",
            media_type="video",
            sha256="33334444555566667777888899990000aaaabbbbccccddddeeeeffff11112222",
            size_bytes=4096,
        ),
        InputFile(
            file_id="f_0004",
            filename="notes.txt",
            media_type="text",
            sha256="4444555566667777888899990000aaaabbbbccccddddeeeeffff111122223333",
            size_bytes=512,
        ),
    ]

    findings = make_stub_findings(inputs)
    assert len(findings) == 4

    for inp, finding in zip(inputs, findings):
        assert finding.source_file_sha256 == inp.sha256
        assert finding.source_file_sha256 != "placeholder"
        assert finding.modality == inp.media_type
        assert finding.analyzer == f"STUB.{inp.media_type}"
        assert finding.analyzer.startswith("STUB.")
        assert "stub" in finding.limitations.lower()
        assert finding.status == "flagged"


# ---------------------------------------------------------------------------
# (c) Unknown file extension produces an 'unavailable' finding with reason
# ---------------------------------------------------------------------------
def test_unknown_extension_make_stub_findings():
    unknown_input = InputFile(
        file_id="f_0005",
        filename="corrupted_file.xyz",
        media_type="unknown",
        sha256="555566667777888899990000aaaabbbbccccddddeeeeffff1111222233334444",
        size_bytes=128,
    )
    findings = make_stub_findings([unknown_input])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.status == "unavailable"
    assert finding.source_file_sha256 == unknown_input.sha256
    assert finding.analyzer == "STUB.unknown"
    assert "xyz" in finding.limitations
    assert len(finding.limitations.strip()) > 0


def test_unknown_extension_pipeline_run_case(tmp_path: Path):
    unknown_file = tmp_path / "sample_unknown.bin"
    unknown_file.write_bytes(b"some random binary payload")
    expected_sha = sha256_file(unknown_file)

    report = run_case([unknown_file], {"caption": "testing unknown extension"})

    assert isinstance(report, Report)
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == "unavailable"
    assert finding.source_file_sha256 == expected_sha
    assert "bin" in finding.limitations
    assert finding.analyzer.startswith("STUB.")
    assert report.inputs[0].media_type == "unknown"


def test_report_created_at_timezone_aware():
    report = Report(
        case_id="c_test_001",
        inputs=[],
        context={},
        findings=[],
        overall=Overall(
            level="low",
            summary="test",
            reasoning="test",
            supporting_findings=[],
            caveats=[],
        ),
        recommended_human_checks=[],
        analysis_log=[],
    )
    # Timezone-aware ISO string should end with +00:00 or Z
    assert "+00:00" in report.created_at or report.created_at.endswith("Z")
