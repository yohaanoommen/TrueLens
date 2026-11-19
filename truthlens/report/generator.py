"""HTML Report generator for TruthLens.

Renders self-contained forensic reports with base64 embedded visual artifacts.
Follows the structure and required sections defined in SPEC.md section 9.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..schemas import Report

TEMPLATE_DIR = Path(__file__).resolve().parent


def _encode_image_to_data_uri(image_path: Path) -> str | None:
    """Read an image file and return its base64 data URI."""
    if not image_path.is_file():
        return None
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def generate_html_report(report: Report, case_dir: str | Path) -> str:
    """Render a standalone, self-contained HTML report string with embedded artifacts.

    Parameters
    ----------
    report:
        The validated Report instance.
    case_dir:
        Directory for the current case where artifacts are located.

    Returns
    -------
    str:
        The self-contained HTML report.
    """
    cd = Path(case_dir)

    # Collect and base64-encode visual evidence
    visual_evidence: List[Dict[str, str]] = []
    seen_refs = set()

    for f in report.findings:
        for ref in f.evidence_refs:
            if ref not in seen_refs:
                seen_refs.add(ref)
                full_path = cd / ref
                data_uri = _encode_image_to_data_uri(full_path)
                if data_uri:
                    visual_evidence.append(
                        {
                            "ref": ref,
                            "data_uri": data_uri,
                            "caption": f"Finding [{f.id}] Artifact: {ref}",
                            "finding_id": f.id,
                        }
                    )

    has_stubs = any(f.analyzer.startswith("STUB.") for f in report.findings)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")

    return template.render(
        report=report,
        visual_evidence=visual_evidence,
        has_stubs=has_stubs,
    )


def save_html_report(report: Report, case_dir: str | Path) -> Path:
    """Generate and write the self-contained HTML report to <case_dir>/report.html."""
    cd = Path(case_dir)
    cd.mkdir(parents=True, exist_ok=True)
    html_content = generate_html_report(report, cd)
    output_path = cd / "report.html"
    output_path.write_text(html_content, encoding="utf-8")
    return output_path
