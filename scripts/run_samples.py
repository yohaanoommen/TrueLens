"""Script to run the TruthLens image analyzer on all sample images.

Prints each finding's analyzer, status, confidence, location, explanation, and limitations.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from truthlens.analyzers import image as image_analyzer

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    samples_dir = REPO_ROOT / "samples"
    if not samples_dir.exists():
        print(f"Samples directory '{samples_dir}' does not exist.")
        return

    image_files = [
        f for f in sorted(samples_dir.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
    ]

    if not image_files:
        print(f"No sample images found in '{samples_dir}'.")
        return

    tmp_case_dir = Path(tempfile.mkdtemp(prefix="truthlens_samples_"))
    print(f"Running image analyzer on {len(image_files)} sample image(s)...")
    print(f"Artifacts output dir: {tmp_case_dir}\n")

    for img_path in image_files:
        print("=" * 70)
        print(f"IMAGE: {img_path.name}")
        print("=" * 70)

        findings = image_analyzer.analyze(str(img_path.resolve()), str(tmp_case_dir))
        print(f"Total findings: {len(findings)}\n")

        for idx, f in enumerate(findings, start=1):
            loc_str = f"{f.location.type}"
            if f.location.bbox:
                loc_str += f" bbox={f.location.bbox}"
            elif f.location.detail:
                loc_str += f" detail='{f.location.detail}'"

            print(f"[{idx}] Analyzer:    {f.analyzer}")
            print(f"    Status:      {f.status}")
            print(f"    Confidence:  {f.confidence}")
            print(f"    Location:    {loc_str}")
            print(f"    Explanation: {f.explanation}")
            print(f"    Limitations: {f.limitations}")
            if f.evidence_refs:
                print(f"    Evidence:    {', '.join(f.evidence_refs)}")
            print("-" * 50)
        print()


if __name__ == "__main__":
    main()
