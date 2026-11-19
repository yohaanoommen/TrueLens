"""Tests for TruthLens schemas, validation, stubs, pipeline, confidence rules, and HTML reporting.

Validates:
(a) Empty or whitespace-only limitations and explanations are rejected.
(b) Stub findings carry the real sha256 and matching modality.
(c) Unknown file extensions produce an 'unavailable' finding with the reason.
(d) Image analyzer handles corrupt files, produces valid Findings, and integrates with pipeline.
(e) ELA reporting cap, confidence calibration, and synthetic splice test.
(f) Lossless PNG metadata and ELA caveat tests.
(g) Stage 2b: Confidence rules (compute_overall) and self-contained HTML report generation.
"""

from __future__ import annotations

import base64
from pathlib import Path
import pytest
from pydantic import ValidationError

from truthlens.analyzers import image as image_analyzer
from truthlens.confidence import compute_overall, generate_recommended_checks
from truthlens.pipeline import run_case
from truthlens.report.generator import generate_html_report, save_html_report
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
    assert "+00:00" in report.created_at or report.created_at.endswith("Z")


# ---------------------------------------------------------------------------
# (d) Stage 2a: Image Analyzer Tests
# ---------------------------------------------------------------------------
def test_image_analyzer_corrupted_file(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.jpg"
    corrupt_file.write_bytes(b"\x00\xff\xfe\x01\x02\x03\x04\x05not_a_valid_image_stream")

    findings = image_analyzer.analyze(str(corrupt_file), str(tmp_path))
    assert len(findings) >= 1
    for f in findings:
        assert isinstance(f, Finding)
        assert f.status == "unavailable"
        assert len(f.limitations.strip()) > 0
        assert f.modality == "image"


def test_image_analyzer_nonexistent_file(tmp_path: Path):
    missing_path = tmp_path / "nonexistent.png"
    findings = image_analyzer.analyze(str(missing_path), str(tmp_path))
    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.status == "unavailable"
    assert "nonexistent.png" in f.explanation
    assert len(f.limitations.strip()) > 0


def test_image_analyzer_sample_images(tmp_path: Path):
    repo_root = Path(__file__).resolve().parent.parent
    sample1 = repo_root / "samples" / "image1.jpeg"
    sample2 = repo_root / "samples" / "image2.jpg"

    if not sample1.exists() or not sample2.exists():
        pytest.skip("Sample images not found in samples/ directory")

    # Analyze sample1 (manipulated image without EXIF)
    findings1 = image_analyzer.analyze(str(sample1), str(tmp_path))
    assert len(findings1) >= 2
    for f in findings1:
        assert isinstance(f, Finding)
        assert len(f.explanation.strip()) > 0
        assert len(f.limitations.strip()) > 0
        assert f.modality == "image"
        assert f.analyzer in ("image.exif", "image.ela")
        for ref in f.evidence_refs:
            assert (tmp_path / ref).exists()

    # Verify sample1 flagged indicators
    analyzers1 = [f.analyzer for f in findings1]
    assert "image.exif" in analyzers1
    assert "image.ela" in analyzers1
    exif_findings1 = [f for f in findings1 if f.analyzer == "image.exif"]
    assert any(f.status == "flagged" for f in exif_findings1)

    # Analyze sample2 (normal image with EXIF)
    findings2 = image_analyzer.analyze(str(sample2), str(tmp_path))
    assert len(findings2) >= 2
    for f in findings2:
        assert isinstance(f, Finding)
        assert len(f.explanation.strip()) > 0
        assert len(f.limitations.strip()) > 0
        for ref in f.evidence_refs:
            assert (tmp_path / ref).exists()

    exif_findings2 = [f for f in findings2 if f.analyzer == "image.exif"]
    assert any(f.status == "clear" for f in exif_findings2)


def test_pipeline_with_real_image():
    repo_root = Path(__file__).resolve().parent.parent
    sample1 = repo_root / "samples" / "image1.jpeg"
    if not sample1.exists():
        pytest.skip("Sample image1 not found")

    report = run_case([sample1], {"caption": "Test real image run"})
    assert isinstance(report, Report)
    assert len(report.inputs) == 1
    assert report.inputs[0].media_type == "image"
    assert len(report.findings) >= 2
    assert any(f.analyzer == "image.ela" for f in report.findings)
    assert not any(f.analyzer.startswith("STUB.") for f in report.findings)
    log_steps = [entry.step for entry in report.analysis_log]
    assert "image.ela" in log_steps


# ---------------------------------------------------------------------------
# (e) ELA reporting cap, confidence calibration, and synthetic splice test
# ---------------------------------------------------------------------------
def test_ela_max_three_regions_reporting(tmp_path: Path):
    repo_root = Path(__file__).resolve().parent.parent
    sample1 = repo_root / "samples" / "image1.jpeg"
    if not sample1.exists():
        pytest.skip("Sample image1 not found")

    findings = image_analyzer.analyze(str(sample1), str(tmp_path))
    ela_findings = [f for f in findings if f.analyzer == "image.ela"]
    assert len(ela_findings) <= 3
    if len(ela_findings) > 0:
        first_ela = ela_findings[0]
        assert "showing the 3 strongest" in first_ela.explanation
        assert first_ela.confidence == "low"
        assert "Widespread differences more likely reflect recompression" in first_ela.explanation


def test_synthetic_spliced_image_ela(tmp_path: Path):
    """Build a synthetic spliced image in code and test whether ELA flags the pasted region."""
    import io
    import numpy as np
    from PIL import Image

    # 1. Smooth background saved as JPEG at quality 95
    bg = Image.new("RGB", (400, 400), color=(180, 200, 220))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    # 2. Textured patch saved at quality 60
    patch_arr = np.random.RandomState(42).randint(0, 255, (100, 100, 3), dtype=np.uint8)
    patch = Image.fromarray(patch_arr)
    p_buf = io.BytesIO()
    patch.save(p_buf, format="JPEG", quality=60)
    p_buf.seek(0)
    patch_jpg = Image.open(p_buf).convert("RGB")

    # 3. Paste patch at (100, 100)
    img.paste(patch_jpg, (100, 100))

    # 4. Re-save spliced image as JPEG at quality 85
    spliced_file = tmp_path / "spliced.jpg"
    img.save(spliced_file, format="JPEG", quality=85)

    # 5. Run image analyzer
    findings = image_analyzer.analyze(str(spliced_file), str(tmp_path))
    ela_findings = [f for f in findings if f.analyzer == "image.ela"]

    flagged_bboxes = [
        f.location.bbox for f in ela_findings if f.status == "flagged" and f.location.bbox
    ]
    pasted_box = [100, 100, 100, 100]

    is_flagged = False
    for bx, by, bw, bh in flagged_bboxes:
        overlap_x = max(0, min(bx + bw, 200) - max(bx, 100))
        overlap_y = max(0, min(by + bh, 200) - max(by, 100))
        if overlap_x > 0 and overlap_y > 0:
            is_flagged = True
            break

    assert is_flagged, f"Expected spliced patch at {pasted_box} to be flagged by ELA, got bboxes: {flagged_bboxes}"


# ---------------------------------------------------------------------------
# (f) Lossless PNG metadata and ELA caveat tests
# ---------------------------------------------------------------------------
def test_png_without_exif_clear_not_flagged(tmp_path: Path):
    """(a) A PNG with no EXIF does not produce a 'flagged' no-EXIF finding."""
    from PIL import Image

    png_path = tmp_path / "clean.png"
    img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    img.save(png_path, format="PNG")

    findings = image_analyzer.analyze(str(png_path), str(tmp_path))
    exif_findings = [f for f in findings if f.analyzer == "image.exif"]

    flagged_no_exif = [
        f
        for f in exif_findings
        if f.status == "flagged" and "missing" in f.indicator.lower()
    ]
    assert len(flagged_no_exif) == 0

    clear_exif = [f for f in exif_findings if f.status == "clear"]
    assert len(clear_exif) >= 1
    assert "not normally present" in clear_exif[0].explanation.lower()
    assert "absent, stripped, or forged" in clear_exif[0].limitations.lower()


def test_png_with_canva_text_chunk_flagged(tmp_path: Path):
    """(b) A PNG with a Canva Software text chunk is still flagged."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    png_path = tmp_path / "canva.png"
    img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    png_info = PngInfo()
    png_info.add_text("Software", "Canva")
    img.save(png_path, format="PNG", pnginfo=png_info)

    findings = image_analyzer.analyze(str(png_path), str(tmp_path))
    flagged_software = [
        f
        for f in findings
        if f.analyzer == "image.exif"
        and f.status == "flagged"
        and "editing software" in f.indicator.lower()
    ]
    assert len(flagged_software) >= 1
    assert "canva" in flagged_software[0].explanation.lower()


def test_png_ela_limitations_contain_jpeg_caveat(tmp_path: Path):
    """(c) The ELA limitations for a PNG contain the new JPEG-design caveat."""
    from PIL import Image

    png_path = tmp_path / "test_ela.png"
    img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    img.save(png_path, format="PNG")

    findings = image_analyzer.analyze(str(png_path), str(tmp_path))
    ela_findings = [f for f in findings if f.analyzer == "image.ela"]
    assert len(ela_findings) >= 1

    expected_caveat = (
        "ELA is designed for JPEG. On lossless images the result mainly reflects "
        "differences in texture and prior compression history, so treat it as a pointer "
        "for human review, not as evidence of editing."
    )
    for f in ela_findings:
        assert expected_caveat in f.limitations


def test_explanation_never_contains_empty_tag(tmp_path: Path):
    """(d) The explanation text never contains 'Tag: '''."""
    repo_root = Path(__file__).resolve().parent.parent
    sample3 = repo_root / "samples" / "image3.png"

    test_paths = [sample3] if sample3.exists() else []

    from PIL import Image

    xmp_png = tmp_path / "xmp_canva.png"
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    img.info["xmp"] = b"<xmp:CreatorTool>Canva</xmp:CreatorTool>"
    img.save(xmp_png, format="PNG")
    test_paths.append(xmp_png)

    for p in test_paths:
        findings = image_analyzer.analyze(str(p), str(tmp_path))
        for f in findings:
            assert "Tag: ''" not in f.explanation


# ---------------------------------------------------------------------------
# (g) Stage 2b: Confidence Rules and HTML Report Generator
# ---------------------------------------------------------------------------
def test_confidence_ignores_stubs_and_unavailable():
    """Findings starting with STUB. and status 'unavailable' are ignored in evidence counting."""
    stub_finding = Finding(
        id="f_stub",
        modality="image",
        analyzer="STUB.image",
        indicator="Stub",
        status="flagged",
        confidence="low",
        location=_make_dummy_location(),
        explanation="Stub explanation.",
        limitations="Stub limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    overall = compute_overall([stub_finding])
    assert overall.level == "inconclusive"
    assert "No non-stub forensic evidence" in overall.summary

    unavail_finding = Finding(
        id="f_unavail",
        modality="image",
        analyzer="image.error",
        indicator="Error",
        status="unavailable",
        confidence="low",
        location=_make_dummy_location(),
        explanation="Error explanation.",
        limitations="Error limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    overall_unavail = compute_overall([unavail_finding])
    assert overall_unavail.level == "inconclusive"


def test_confidence_multiple_findings_same_analyzer_counts_as_one_method():
    """Multiple findings from the same analyzer (e.g. 3 ELA regions) count as ONE method (low level)."""
    f1 = Finding(
        id="f_ela_01",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region 1.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f2 = Finding(
        id="f_ela_02",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region 2.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f3 = Finding(
        id="f_ela_03",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region 3.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )

    overall = compute_overall([f1, f2, f3])
    # Only 1 independent method -> must be "low", NOT "medium" or "high"
    assert overall.level == "low"
    assert len(overall.supporting_findings) == 3


def test_confidence_two_independent_methods_reaches_medium():
    """Two independent flagged methods (e.g. image.exif + image.ela) reach 'medium'."""
    f_exif = Finding(
        id="f_exif",
        modality="image",
        analyzer="image.exif",
        indicator="Editing software",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Canva detected.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f_ela = Finding(
        id="f_ela",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )

    overall = compute_overall([f_exif, f_ela])
    assert overall.level == "medium"
    assert "2 independent forensic method(s)" in overall.reasoning


def test_confidence_image_only_cannot_reach_high():
    """Image-only evidence can never reach 'high' even with 3+ findings and 2 methods."""
    f_exif = Finding(
        id="f_exif",
        modality="image",
        analyzer="image.exif",
        indicator="Editing software",
        status="flagged",
        confidence="high",
        location=_make_dummy_location(),
        explanation="Photoshop detected.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f_ela1 = Finding(
        id="f_ela1",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region 1.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f_ela2 = Finding(
        id="f_ela2",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region 2.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )

    overall = compute_overall([f_exif, f_ela1, f_ela2])
    # Capped below 'high' because all modalities are 'image'
    assert overall.level == "medium"
    assert "Image-only evidence is capped below 'high'" in overall.reasoning


def test_confidence_multi_modal_can_reach_high():
    """3+ flagged findings from >= 2 methods AND multi-modal agreement reaches 'high'."""
    f_exif = Finding(
        id="f_exif",
        modality="image",
        analyzer="image.exif",
        indicator="Editing software",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Photoshop.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f_ela = Finding(
        id="f_ela",
        modality="image",
        analyzer="image.ela",
        indicator="ELA",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Region.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    f_audio = Finding(
        id="f_audio",
        modality="audio",
        analyzer="audio.synthetic_speech",
        indicator="Synthetic voice detected",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Synthetic voice markers.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="def",
    )

    overall = compute_overall([f_exif, f_ela, f_audio])
    assert overall.level == "high"


def test_confidence_reasoning_and_caveats():
    """Reasoning specifies why chosen and what would change it; caveats state rule-based."""
    f = Finding(
        id="f_exif",
        modality="image",
        analyzer="image.exif",
        indicator="Editing software",
        status="flagged",
        confidence="medium",
        location=_make_dummy_location(),
        explanation="Photoshop.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    overall = compute_overall([f])
    assert "why" in overall.reasoning.lower() or "was assigned" in overall.reasoning.lower()
    assert "change" in overall.reasoning.lower() or "elevate" in overall.reasoning.lower()
    assert any("rule-based" in c.lower() for c in overall.caveats)
    assert any("statistically calibrated" in c.lower() for c in overall.caveats)


def test_dynamic_human_checks_generation():
    """Checks are generated dynamically from actual findings."""
    f1 = Finding(
        id="f_exif_missing",
        modality="image",
        analyzer="image.exif",
        indicator="Missing EXIF metadata",
        status="flagged",
        confidence="low",
        location=_make_dummy_location(),
        explanation="Missing EXIF.",
        limitations="Limitation.",
        evidence_refs=[],
        source_file_sha256="abc",
    )
    checks = generate_recommended_checks([f1])
    assert any("original" in c.lower() for c in checks)


def test_html_report_generation(tmp_path: Path):
    """Test self-contained HTML report generation with base64 embedded images."""
    from PIL import Image

    # 1. Create a dummy artifact image in tmp_path/artifacts/test_ela.png
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    art_path = artifacts_dir / "test_ela.png"
    Image.new("RGB", (64, 64), color=(255, 0, 0)).save(art_path, format="PNG")

    # 2. Build Report
    f = Finding(
        id="f_test_01",
        modality="image",
        analyzer="image.ela",
        indicator="Inconsistent compression",
        status="flagged",
        confidence="medium",
        raw_score=0.72,
        location=Location(type="region", bbox=[10, 10, 20, 20]),
        explanation="Test explanation.",
        limitations="Test limitations.",
        evidence_refs=["artifacts/test_ela.png"],
        source_file_sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    )
    overall = Overall(
        level="medium",
        summary="Test summary.",
        reasoning="Test reasoning.",
        supporting_findings=["f_test_01"],
        caveats=["Test caveat."],
    )
    report = Report(
        case_id="c_test_case_999",
        inputs=[
            InputFile(
                file_id="inp_01",
                filename="evidence.jpg",
                media_type="image",
                sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                size_bytes=54321,
            )
        ],
        context={"caption": "Test claim"},
        findings=[f],
        overall=overall,
        recommended_human_checks=["Check source authenticity."],
        analysis_log=[
            LogEntry(
                time="2026-11-19T10:00:00Z",
                step="image.ela",
                file="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                result="ok",
                note="Completed ok",
            )
        ],
    )

    # 3. Generate HTML
    html_output = generate_html_report(report, tmp_path)
    assert isinstance(html_output, str)
    assert "TruthLens Forensic Report" in html_output
    assert "c_test_case_999" in html_output
    assert "2. Overall Assessment" in html_output
    assert "3. Flagged Evidence Table" in html_output
    assert "4. Visual Evidence" in html_output
    assert "5. Cross-Modal Context" in html_output
    assert "6. Per-Finding Detail" in html_output
    assert "7. Recommended Human Checks" in html_output
    assert "8. Analysis Log" in html_output
    assert "Automated indicators only. Not a final verdict. Requires review by a human investigator." in html_output

    # Check base64 embedding
    assert "data:image/png;base64," in html_output

    # Test saving HTML report
    out_file = save_html_report(report, tmp_path)
    assert out_file.exists()
    assert out_file.stat().st_size > 500
