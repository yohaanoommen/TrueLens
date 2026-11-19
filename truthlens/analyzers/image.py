"""Image forensic analyzers for TruthLens.

Implements:
1. EXIF and metadata inspection (exifread + Pillow PNG chunks).
2. Error Level Analysis (ELA) with heatmap artifact generation and outlier region detection.
Follows the analyzer interface in SPEC.md section 5.3 and failure behavior in 5.2.
Never modifies original evidence; catches all exceptions and returns 'unavailable' findings.
"""

from __future__ import annotations

import io
from collections import deque
from pathlib import Path
from typing import List, Literal, Tuple

import exifread
import numpy as np
from PIL import Image

from ..schemas import Finding, Location
from ..storage import sha256_file

EDITING_SOFTWARE_KEYWORDS = [
    "photoshop",
    "gimp",
    "lightroom",
    "canva",
    "snapseed",
    "vsco",
    "pixlr",
    "pixelmator",
    "paint.net",
    "photopea",
    "affinity",
    "coreldraw",
    "capture one",
]

AI_GENERATOR_KEYWORDS = [
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "comfyui",
    "novelai",
    "automatic1111",
    "adobe firefly",
    "bing image creator",
    "flux",
    "stablediffusion",
    "dreamstudio",
]

LOSSLESS_FORMATS = {"PNG", "BMP", "TIFF", "GIF"}
LOSSLESS_EXTENSIONS = {".png", ".bmp", ".tiff", ".tif", ".gif"}


def _is_lossless(img: Image.Image, path: Path) -> bool:
    """Return True if image is in a lossless format where camera EXIF is not expected."""
    fmt = (getattr(img, "format", "") or "").upper()
    if fmt in LOSSLESS_FORMATS or path.suffix.lower() in LOSSLESS_EXTENSIONS:
        return True
    if fmt == "WEBP" and img.info.get("lossless"):
        return True
    return False


def _check_metadata(path: Path, sha256_str: str, img: Image.Image) -> List[Finding]:
    """Inspect EXIF tags and PNG/Pillow text chunks for manipulation signals."""
    findings: List[Finding] = []

    # Read EXIF using exifread in read-only binary mode
    with path.open("rb") as f:
        tags = exifread.process_file(f, details=False)

    make = str(tags.get("Image Make", "")).strip()
    model = str(tags.get("Image Model", "")).strip()
    software = str(tags.get("Image Software", "")).strip()
    date_original = str(
        tags.get("EXIF DateTimeOriginal", tags.get("Image DateTime", ""))
    ).strip()
    has_gps = any(k.startswith("GPS") for k in tags.keys())

    # Read extra text chunks from Pillow (e.g. PNG text or XMP)
    extra_text_parts: List[str] = []
    if hasattr(img, "info") and isinstance(img.info, dict):
        for k, v in img.info.items():
            if isinstance(v, (str, bytes)):
                v_str = (
                    v.decode("utf-8", errors="ignore")
                    if isinstance(v, bytes)
                    else str(v)
                )
                extra_text_parts.append(f"{k}: {v_str}")
    combined_extra_text = " | ".join(extra_text_parts)

    # 1. Check for AI generator markers in tags and chunks
    matched_ai: List[str] = []
    for k, v in tags.items():
        v_str = str(v).lower()
        for kw in AI_GENERATOR_KEYWORDS:
            if kw in v_str and kw not in matched_ai:
                matched_ai.append(kw)

    lower_extra = combined_extra_text.lower()
    for kw in AI_GENERATOR_KEYWORDS:
        if kw in lower_extra and kw not in matched_ai:
            matched_ai.append(kw)

    if matched_ai:
        findings.append(
            Finding(
                id="f_exif_ai",
                modality="image",
                analyzer="image.exif",
                indicator="Generative AI tool markers found in metadata",
                status="flagged",
                confidence="medium",
                raw_score=0.85,
                location=Location(type="metadata", detail="AI marker"),
                explanation=(
                    f"Metadata contains signatures associated with generative AI tools: "
                    f"{', '.join(matched_ai)}."
                ),
                limitations=(
                    "Metadata markers can be manually edited, injected, or stripped; "
                    "they must be correlated with visual and frequency analysis."
                ),
                evidence_refs=[],
                source_file_sha256=sha256_str,
            )
        )

    # 2. Check for editing software in Software tag and text chunks
    matched_editing: List[str] = []
    check_software_str = f"{software} {combined_extra_text}".lower()
    for kw in EDITING_SOFTWARE_KEYWORDS:
        if kw in check_software_str and kw not in matched_editing:
            matched_editing.append(kw)

    if matched_editing:
        tag_info = f" (Tag: '{software}')" if software else ""
        findings.append(
            Finding(
                id="f_exif_software",
                modality="image",
                analyzer="image.exif",
                indicator="Image editing software detected in metadata",
                status="flagged",
                confidence="medium",
                raw_score=0.75,
                location=Location(type="metadata", detail="Software"),
                explanation=(
                    f"Metadata indicates image was processed with editing software: "
                    f"{', '.join(matched_editing)}{tag_info}."
                ),
                limitations=(
                    "Editing software tags indicate post-processing or re-saving, but "
                    "do not prove malicious manipulation or deepfake creation."
                ),
                evidence_refs=[],
                source_file_sha256=sha256_str,
            )
        )

    is_lossless = _is_lossless(img, path)
    fmt_name = (
        getattr(img, "format", "") or path.suffix.lstrip(".").upper()
    ) or "lossless"

    # 3. If there is NO EXIF metadata at all
    if not tags:
        if is_lossless:
            # Lossless formats (PNG, BMP, TIFF, GIF, WebP-lossless) do not normally carry camera EXIF.
            # Missing EXIF is expected and not suspicious.
            if not matched_ai and not matched_editing:
                findings.append(
                    Finding(
                        id="f_exif_lossless",
                        modality="image",
                        analyzer="image.exif",
                        indicator="Metadata absent (normal for format)",
                        status="clear",
                        confidence="low",
                        raw_score=None,
                        location=Location(type="file"),
                        explanation=(
                            f"Camera EXIF is not normally present in {fmt_name} files, "
                            "so its absence is expected and not suspicious."
                        ),
                        limitations=(
                            "Camera EXIF metadata can be absent, stripped, or forged. "
                            "The absence of metadata in a lossless file is normal and not evidence of tampering."
                        ),
                        evidence_refs=[],
                        source_file_sha256=sha256_str,
                    )
                )
        else:
            # Lossy camera format (e.g. JPEG) with missing EXIF is suspicious
            findings.append(
                Finding(
                    id="f_exif_missing",
                    modality="image",
                    analyzer="image.exif",
                    indicator="Missing EXIF metadata",
                    status="flagged",
                    confidence="low",
                    raw_score=None,
                    location=Location(type="file"),
                    explanation="No EXIF metadata was found in the image file.",
                    limitations=(
                        "Messaging apps (WhatsApp etc.) and social platforms strip metadata, "
                        "so missing EXIF is weak evidence of manipulation."
                    ),
                    evidence_refs=[],
                    source_file_sha256=sha256_str,
                )
            )
    elif not matched_ai and not matched_editing:
        # 4. If metadata is present and looks normal
        details_list = []
        if make or model:
            details_list.append(f"Camera: {make} {model}".strip())
        if software:
            details_list.append(f"Software: {software}")
        if date_original:
            details_list.append(f"Date: {date_original}")
        if has_gps:
            details_list.append("GPS: present")
        details_str = ", ".join(details_list) if details_list else "EXIF tags present"

        findings.append(
            Finding(
                id="f_exif_normal",
                modality="image",
                analyzer="image.exif",
                indicator="Camera metadata present",
                status="clear",
                confidence="low",
                raw_score=None,
                location=Location(type="metadata", detail="EXIF"),
                explanation=(
                    f"Metadata is present and contains standard attributes ({details_str}). "
                    "No known editing software or AI generator signatures were detected."
                ),
                limitations=(
                    "Camera EXIF metadata can be easily spoofed, stripped, or preserved "
                    "across subtle manipulations. Clean metadata is not conclusive proof of authenticity."
                ),
                evidence_refs=[],
                source_file_sha256=sha256_str,
            )
        )

    return findings


def _merge_boxes(boxes: List[List[int]]) -> List[List[int]]:
    """Merge overlapping or adjacent bounding boxes [x, y, w, h]."""
    if not boxes:
        return []

    rects = [[b[0], b[1], b[0] + b[2], b[1] + b[3]] for b in boxes]
    changed = True
    while changed:
        changed = False
        new_rects: List[List[int]] = []
        while rects:
            curr = rects.pop(0)
            merged = False
            for i, other in enumerate(new_rects):
                margin = 16
                if not (
                    curr[2] + margin < other[0]
                    or curr[0] - margin > other[2]
                    or curr[3] + margin < other[1]
                    or curr[1] - margin > other[3]
                ):
                    new_rects[i] = [
                        min(curr[0], other[0]),
                        min(curr[1], other[1]),
                        max(curr[2], other[2]),
                        max(curr[3], other[3]),
                    ]
                    merged = True
                    changed = True
                    break
            if not merged:
                new_rects.append(curr)
        rects = new_rects

    result = []
    for r in rects:
        result.append([r[0], r[1], r[2] - r[0], r[3] - r[1]])
    result.sort(key=lambda b: b[2] * b[3], reverse=True)
    return result


def _run_ela(
    path: Path, case_dir: Path, sha256_str: str, img: Image.Image
) -> List[Finding]:
    """Perform Error Level Analysis (ELA) and return findings with heatmap artifact."""
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    sha_prefix = sha256_str[:12]
    ela_rel_path = f"artifacts/{sha_prefix}_ela.png"
    ela_abs_path = case_dir / ela_rel_path

    is_lossless = _is_lossless(img, path)
    lossless_caveat = (
        " ELA is designed for JPEG. On lossless images the result mainly reflects "
        "differences in texture and prior compression history, so treat it as a pointer "
        "for human review, not as evidence of editing."
        if is_lossless
        else ""
    )

    # Convert original to RGB
    rgb_img = img.convert("RGB")
    arr_orig = np.asarray(rgb_img, dtype=np.float32)

    # Re-save as JPEG at quality 90 into in-memory buffer
    buf = io.BytesIO()
    rgb_img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    resaved_img = Image.open(buf).convert("RGB")
    arr_resaved = np.asarray(resaved_img, dtype=np.float32)

    # Compute per-pixel difference
    diff = np.abs(arr_orig - arr_resaved)
    err = np.mean(diff, axis=2)

    # Scale for visibility and save heatmap PNG
    scale_factor = 15.0
    scaled_vis = np.clip(diff * scale_factor, 0, 255).astype(np.uint8)
    heatmap_img = Image.fromarray(scaled_vis)
    heatmap_img.save(ela_abs_path, format="PNG")

    # Divide error image into blocks
    H, W = err.shape
    block_size = 32
    if H < 64 or W < 64:
        block_size = max(8, min(H, W) // 4)

    n_rows = H // block_size
    n_cols = W // block_size

    if n_rows < 2 or n_cols < 2:
        return [
            Finding(
                id="f_ela_clear",
                modality="image",
                analyzer="image.ela",
                indicator="Uniform compression error level",
                status="clear",
                confidence="low",
                raw_score=0.0,
                location=Location(type="file"),
                explanation="Error Level Analysis completed; image dimensions are too small to reliably isolate anomalous compression blocks.",
                limitations=(
                    "ELA also produces false positives on re-saved, resized, or heavily compressed images "
                    f"and is not conclusive alone.{lossless_caveat}"
                ),
                evidence_refs=[ela_rel_path],
                source_file_sha256=sha256_str,
            )
        ]

    block_means = np.zeros((n_rows, n_cols), dtype=np.float32)
    for r in range(n_rows):
        for c in range(n_cols):
            block_means[r, c] = np.mean(
                err[
                    r * block_size : (r + 1) * block_size,
                    c * block_size : (c + 1) * block_size,
                ]
            )

    global_mean = float(np.mean(block_means))
    global_std = float(np.std(block_means))

    # Outlier threshold: mean + 2.5 * std, with a minimum absolute threshold to prevent noise
    outlier_threshold = max(global_mean + 2.5 * global_std, global_mean + 1.0)
    outlier_mask = block_means > outlier_threshold

    num_outliers = int(np.sum(outlier_mask))
    total_blocks = n_rows * n_cols
    outlier_coverage = num_outliers / total_blocks if total_blocks > 0 else 0.0

    # Find connected components of outlier blocks
    visited = set()
    components: List[List[Tuple[int, int]]] = []
    for r in range(n_rows):
        for c in range(n_cols):
            if outlier_mask[r, c] and (r, c) not in visited:
                comp = []
                q = deque([(r, c)])
                visited.add((r, c))
                while q:
                    cr, cc = q.popleft()
                    comp.append((cr, cc))
                    for dr, dc in [
                        (-1, 0),
                        (1, 0),
                        (0, -1),
                        (0, 1),
                        (-1, -1),
                        (-1, 1),
                        (1, -1),
                        (1, 1),
                    ]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < n_rows and 0 <= nc < n_cols:
                            if outlier_mask[nr, nc] and (nr, nc) not in visited:
                                visited.add((nr, nc))
                                q.append((nr, nc))
                components.append(comp)

    # Merge into bounding boxes
    raw_boxes: List[List[int]] = []
    for comp in components:
        min_r = min(cell[0] for cell in comp)
        max_r = max(cell[0] for cell in comp)
        min_c = min(cell[1] for cell in comp)
        max_c = max(cell[1] for cell in comp)
        bx = int(min_c * block_size)
        by = int(min_r * block_size)
        bw = int(min(W - bx, (max_c - min_c + 1) * block_size))
        bh = int(min(H - by, (max_r - min_r + 1) * block_size))
        raw_boxes.append([bx, by, bw, bh])

    merged_boxes = _merge_boxes(raw_boxes)
    total_regions = len(merged_boxes)

    if not merged_boxes:
        return [
            Finding(
                id="f_ela_clear",
                modality="image",
                analyzer="image.ela",
                indicator="Uniform compression error level",
                status="clear",
                confidence="low",
                raw_score=0.0,
                location=Location(type="file"),
                explanation="Error Level Analysis shows relatively uniform compression behavior across the image with no localized error spikes.",
                limitations=(
                    "ELA also produces false positives on re-saved, resized, or heavily compressed images "
                    f"and is not conclusive alone.{lossless_caveat}"
                ),
                evidence_refs=[ela_rel_path],
                source_file_sha256=sha256_str,
            )
        ]

    # Calculate score/strength for each merged box and rank them
    scored_boxes: List[Tuple[List[int], float, float]] = []
    for bbox in merged_boxes:
        bx, by, bw, bh = bbox
        sub_err = err[by : by + bh, bx : bx + bw]
        mean_sub = float(np.mean(sub_err)) if sub_err.size > 0 else global_mean
        score = min(
            1.0, max(0.0, (mean_sub - global_mean) / (global_std * 5.0 + 1e-6))
        )
        scored_boxes.append((bbox, mean_sub, round(score, 2)))

    # Rank by mean_sub descending (strongest outliers first)
    scored_boxes.sort(key=lambda item: item[1], reverse=True)

    # Confidence rules:
    # If outlier blocks cover > 15% of the image, or > 3 regions were found:
    # set confidence to "low" and explain that widespread differences more likely reflect recompression.
    # Use "medium" only for 1 to 2 localized regions.
    is_widespread = (outlier_coverage > 0.15) or (total_regions > 3)
    if is_widespread:
        ela_confidence: Literal["low", "medium", "high"] = "low"
    elif 1 <= total_regions <= 2:
        ela_confidence = "medium"
    else:
        ela_confidence = "low"

    widespread_note = (
        " Widespread differences more likely reflect recompression (for example by a messaging app) than local editing."
        if is_widespread
        else ""
    )

    # Return at most the 3 strongest outlier regions
    top_boxes = scored_boxes[:3]
    findings: List[Finding] = []

    for idx, (bbox, mean_sub, score) in enumerate(top_boxes, start=1):
        bx, by, bw, bh = bbox

        # If more were found, say so in the explanation of the first one
        if idx == 1 and total_regions > 3:
            prefix = f"{total_regions} regions found; showing the 3 strongest. "
        else:
            prefix = ""

        explanation = (
            f"{prefix}A localized region at [{bx}, {by}, {bw}, {bh}] compresses differently "
            f"from the background, which may indicate local editing or a different compression history.{widespread_note}"
        )

        findings.append(
            Finding(
                id=f"f_ela_region_{idx:02d}",
                modality="image",
                analyzer="image.ela",
                indicator="Inconsistent compression levels",
                status="flagged",
                confidence=ela_confidence,
                raw_score=score,
                location=Location(type="region", bbox=bbox),
                explanation=explanation,
                limitations=(
                    "ELA also produces false positives on re-saved, resized, or heavily compressed "
                    f"images, as well as high-contrast edges. Not conclusive on its own.{lossless_caveat}"
                ),
                evidence_refs=[ela_rel_path],
                source_file_sha256=sha256_str,
            )
        )

    return findings


def analyze(
    path: str, case_dir: str, context: dict | None = None
) -> List[Finding]:
    """Analyze an image file for forensic indicators.

    Parameters
    ----------
    path:
        Absolute path to the original file (read-only, never modify).
    case_dir:
        Directory for the current case; artifacts are written to <case_dir>/artifacts/.
    context:
        Optional extras (caption, claimed date, etc.).

    Returns
    -------
    List[Finding]:
        Forensic findings. Catch all exceptions and return 'unavailable' findings.
    """
    p = Path(path)
    cd = Path(case_dir)

    try:
        sha256_str = sha256_file(p)
    except Exception as exc:
        return [
            Finding(
                id="f_img_unavailable",
                modality="image",
                analyzer="image.error",
                indicator="File unreadable",
                status="unavailable",
                confidence="low",
                raw_score=None,
                location=Location(type="file"),
                explanation=f"Cannot read file '{p.name}'.",
                limitations=f"Failed to access or hash file: {type(exc).__name__}: {str(exc)}",
                evidence_refs=[],
                source_file_sha256="unavailable",
            )
        ]

    try:
        with Image.open(p) as img:
            img.load()
            metadata_findings = _check_metadata(p, sha256_str, img)
            ela_findings = _run_ela(p, cd, sha256_str, img)
            return metadata_findings + ela_findings
    except Exception as exc:
        return [
            Finding(
                id="f_img_unavailable",
                modality="image",
                analyzer="image.error",
                indicator="Decoding failed",
                status="unavailable",
                confidence="low",
                raw_score=None,
                location=Location(type="file"),
                explanation=f"Image decoding failed for '{p.name}'.",
                limitations=f"Failed to decode image data: {type(exc).__name__}: {str(exc)}",
                evidence_refs=[],
                source_file_sha256=sha256_str,
            )
        ]
