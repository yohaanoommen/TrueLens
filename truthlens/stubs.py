"""Stub findings generation for Stage 1.

Generates deterministic placeholder findings for uploaded files during UI and
pipeline development. All analyzers are prefixed with ``STUB.`` and limitations
explicitly document that real analysis is not implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .schemas import Finding, InputFile, Location


def make_stub_findings(input_files: List[InputFile]) -> List[Finding]:
    """Generate one stub finding per input file.

    Parameters
    ----------
    input_files:
        List of InputFile instances representing stored original uploads.

    Returns
    -------
    List[Finding]:
        List of Finding instances corresponding to each input file.
    """
    findings: List[Finding] = []
    for idx, f in enumerate(input_files, start=1):
        if f.media_type == "unknown":
            suffix = Path(f.filename).suffix
            findings.append(
                Finding(
                    id=f"f_stub_{idx:03d}",
                    modality=f.media_type,
                    analyzer=f"STUB.{f.media_type}",
                    indicator="Unsupported file extension",
                    status="unavailable",
                    confidence="low",
                    raw_score=None,
                    location=Location(type="file"),
                    explanation=f"File '{f.filename}' has an unsupported file extension.",
                    limitations=(
                        f"Unsupported file extension '{suffix}'. Supported extensions: "
                        "jpg, jpeg, png, webp, mp4, mov, avi, mkv, wav, mp3, m4a, flac, txt, md (stub analyzer)."
                    ),
                    evidence_refs=[],
                    source_file_sha256=f.sha256,
                )
            )
        else:
            findings.append(
                Finding(
                    id=f"f_stub_{idx:03d}",
                    modality=f.media_type,
                    analyzer=f"STUB.{f.media_type}",
                    indicator=f"Sample {f.media_type} artifact",
                    status="flagged",
                    confidence="low",
                    raw_score=None,
                    location=Location(type="file"),
                    explanation=f"This is a stub finding for {f.media_type} file '{f.filename}'.",
                    limitations="Stub finding – real analysis not implemented.",
                    evidence_refs=[],
                    source_file_sha256=f.sha256,
                )
            )
    return findings
