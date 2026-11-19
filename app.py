"""Streamlit UI for TruthLens Stage 1.

The UI allows the user to upload one or more files, optionally provide a caption,
and then run the ``run_case`` pipeline which currently returns stub findings.
The resulting findings are displayed with their ``limitations`` and a JSON
report can be downloaded.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import streamlit as st

from truthlens.pipeline import run_case
from truthlens.schemas import Finding, Report

st.set_page_config(page_title="TruthLens – Stage 1", layout="centered")

st.title("TruthLens – Stage 1 (Skeleton)")

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

        # Display findings.
        st.subheader("Findings")
        if report.findings:
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
                    st.write(f"**Explanation:** {f.explanation}")
                    st.write(f"**Limitations:** {f.limitations}")
                    st.write(f"**Source SHA256:** `{f.source_file_sha256}`")
        else:
            st.info("No findings were generated.")

        # Provide JSON download.
        json_str = report.model_dump_json(indent=2)
        st.download_button(
            label="Download report JSON",
            data=json_str,
            file_name=f"{report.case_id}_report.json",
            mime="application/json",
        )
