"""Streamlit UI for TruthLens.

The UI allows the user to upload one or more files, optionally provide a caption,
and runs the TruthLens analysis pipeline.
Displays findings, limitations, visual evidence, and provides JSON/HTML report downloads.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import streamlit as st

from truthlens.pipeline import run_case
from truthlens.report.generator import generate_html_report
from truthlens.schemas import Finding, Report

st.set_page_config(page_title="TruthLens – Digital Forensics", layout="centered")

st.title("TruthLens – Multimodal Digital Forensics")

uploaded_files = st.file_uploader(
    "Upload evidence files (images, video, audio, text)",
    accept_multiple_files=True,
    type=None,
)
caption = st.text_area(
    "Caption / claim (optional)",
    placeholder="Enter a caption or claim about the evidence",
)

if st.button("Analyze"):
    if not uploaded_files:
        st.warning("Please upload at least one file before analyzing.")
    else:
        # Save uploaded files to a temporary directory.
        temp_dir = Path(tempfile.mkdtemp())
        file_paths: List[Path] = []
        for uf in uploaded_files:
            dest = temp_dir / uf.name
            dest.write_bytes(uf.getvalue())
            file_paths.append(dest)

        # Run the pipeline.
        with st.spinner("Running analysis…"):
            report: Report = run_case(
                file_paths, {"caption": caption} if caption else {}
            )

        # Show demo warning banner if any finding's analyzer starts with "STUB."
        if any(f.analyzer.startswith("STUB.") for f in report.findings):
            st.warning("Demo mode: these are placeholder findings, not real analysis.")

        # Overall summary card
        st.subheader("Overall Assessment")
        st.markdown(f"**Confidence Level:** `{report.overall.level.upper()}`")
        st.markdown(f"**Summary:** {report.overall.summary}")
        st.markdown(f"**Reasoning:** {report.overall.reasoning}")
        if report.overall.caveats:
            st.markdown("**Caveats:**")
            for caveat in report.overall.caveats:
                st.markdown(f"- *{caveat}*")

        # Display findings.
        st.subheader("Findings")
        if report.findings:
            case_dir = Path("data") / "cases" / report.case_id
            for f in report.findings:
                status_label = (
                    f" [{f.status.upper()}]" if f.status == "unavailable" else ""
                )
                expander = st.expander(
                    f"{f.modality.upper()} – {f.indicator} ({f.status}){status_label}"
                )
                with expander:
                    st.write(f"**Analyzer:** `{f.analyzer}`")
                    st.write(f"**Confidence:** {f.confidence}")
                    if f.raw_score is not None:
                        st.write(f"**Raw Score:** {f.raw_score}")
                    st.write(f"**Explanation:** {f.explanation}")
                    st.write(f"**Limitations:** {f.limitations}")
                    st.write(f"**Source SHA256:** `{f.source_file_sha256}`")
                    if f.location.bbox:
                        st.write(f"**Flagged Region (bbox):** `{f.location.bbox}`")
                    if f.evidence_refs:
                        for ref in f.evidence_refs:
                            evidence_path = case_dir / ref
                            if evidence_path.exists():
                                st.image(
                                    str(evidence_path),
                                    caption=f"Evidence: {ref}",
                                    use_container_width=True,
                                )
        else:
            st.info("No findings were generated.")

        # Display recommended human checks
        if report.recommended_human_checks:
            st.subheader("Recommended Human Checks")
            for check in report.recommended_human_checks:
                st.markdown(f"- {check}")

        # Provide JSON and HTML downloads.
        col1, col2 = st.columns(2)
        with col1:
            json_str = report.model_dump_json(indent=2)
            st.download_button(
                label="Download Report JSON",
                data=json_str,
                file_name=f"{report.case_id}_report.json",
                mime="application/json",
            )
        with col2:
            html_path = case_dir / "report.html"
            if html_path.exists():
                html_content = html_path.read_text(encoding="utf-8")
            else:
                html_content = generate_html_report(report, case_dir)
            st.download_button(
                label="Download Report HTML",
                data=html_content,
                file_name=f"{report.case_id}_report.html",
                mime="text/html",
            )
