"""Rule-based forensic confidence computation for TruthLens.

Implements the transparent confidence rules defined in SPEC.md section 8.
Confidence is not statistically calibrated; it is a deterministic rule-based
mapping that explains why a level was assigned and what evidence would change it.
"""

from __future__ import annotations

from typing import List, Literal, Set

from .schemas import Finding, Overall


def generate_recommended_checks(findings: List[Finding]) -> List[str]:
    """Derive dynamic recommended human checks from the actual findings."""
    checks: List[str] = []

    # Inspect findings to determine relevant forensic follow-ups
    for f in findings:
        if f.status == "unavailable":
            msg = f"Verify file integrity and format support for '{f.analyzer}' step."
            if msg not in checks:
                checks.append(msg)
        elif f.status == "flagged":
            if f.analyzer == "image.exif":
                if "missing" in f.indicator.lower():
                    msg = (
                        "Request the original, camera-direct file from the source to "
                        "inspect unstripped EXIF tags."
                    )
                    if msg not in checks:
                        checks.append(msg)
                elif "editing software" in f.indicator.lower():
                    msg = (
                        "Review editing software history to determine if adjustments "
                        "were cosmetic/resizing versus localized content splicing."
                    )
                    if msg not in checks:
                        checks.append(msg)
                elif "generative ai" in f.indicator.lower():
                    msg = (
                        "Audit generation metadata, model parameters, and prompt signatures "
                        "to verify synthetic origin."
                    )
                    if msg not in checks:
                        checks.append(msg)
            elif f.analyzer == "image.ela":
                msg = (
                    "Inspect flagged high-error compression regions under magnification "
                    "to distinguish genuine splicing from natural edge contrast differences."
                )
                if msg not in checks:
                    checks.append(msg)

    # Universal investigative best practices
    if not checks:
        checks.append("Verify the original source, chain of custody, and acquisition context.")
    else:
        checks.append("Cross-reference automated indicators with independent corroborating sources.")

    return checks


def compute_overall(findings: List[Finding]) -> Overall:
    """Compute the overall forensic assessment according to SPEC section 8.

    Rules:
    - Ignore findings whose analyzer starts with 'STUB.' and findings with status 'unavailable'
      when counting evidence.
    - Several findings from the same analyzer count as ONE method.
    - 'high': 3+ flagged findings from >= 2 independent methods AND agreement across
      modalities or a cross-modal finding. Image-only evidence can never reach 'high'.
    - 'medium': 2 independent flagged methods, or 1 'high' finding supported by another.
    - 'low': a single flagged finding or only weak signals.
    - 'inconclusive': conflicting findings, or most analyzers unavailable, or no real findings.
    """
    # 1. Filter out stubs and unavailable findings for evidence counting
    real_findings = [
        f for f in findings
        if not f.analyzer.startswith("STUB.") and f.status != "unavailable"
    ]
    unavailable_findings = [f for f in findings if f.status == "unavailable"]
    real_flagged = [f for f in real_findings if f.status == "flagged"]

    # 2. Check for "inconclusive" edge cases
    # (a) No real non-stub findings
    if not real_findings:
        return Overall(
            level="inconclusive",
            summary="No non-stub forensic evidence available.",
            reasoning=(
                "All findings were placeholders (stubs) or failed execution. No real forensic "
                "analyzers provided valid signals. Running real analyzers on supported original "
                "media would provide actionable forensic signals."
            ),
            supporting_findings=[],
            caveats=[
                "Assessment is rule-based and not statistically calibrated.",
                "Stub and placeholder analyzers do not contribute to forensic confidence.",
            ],
        )

    # (b) Most analyzers unavailable
    total_steps = len(findings)
    if len(unavailable_findings) > 0 and len(unavailable_findings) >= len(real_findings):
        return Overall(
            level="inconclusive",
            summary="Assessment inconclusive due to unavailable analyzers.",
            reasoning=(
                f"{len(unavailable_findings)} of {total_steps} analyzer step(s) were unavailable. "
                "A conclusive forensic determination requires successful analyzer execution across all targets. "
                "Resolving file decoding errors or format issues to allow analyzers to complete would provide "
                "conclusive evidence."
            ),
            supporting_findings=[f.id for f in real_flagged],
            caveats=[
                "Assessment is rule-based and not statistically calibrated.",
                "Unavailable analyzer steps may hide critical indicators of manipulation.",
            ],
        )

    # 3. Analyze independent methods and modalities
    flagged_methods: Set[str] = {f.analyzer for f in real_flagged}
    flagged_modalities: Set[str] = {f.modality for f in real_flagged}
    has_cross_modal = any(f.modality == "cross_modal" for f in real_flagged)
    has_high_conf_finding = any(f.confidence == "high" for f in real_flagged)

    supporting_ids = [f.id for f in real_flagged]

    caveats = [
        "Assessment is rule-based and not statistically calibrated.",
        "Forensic detection scores are indicators, not final verdicts, and require human review.",
    ]

    # 4. Check for 'high' level
    # 3+ flagged findings from >= 2 independent methods AND agreement across modalities or cross-modal.
    # Image-only evidence can never reach "high".
    is_multi_modal = len(flagged_modalities) >= 2 or has_cross_modal
    if len(real_flagged) >= 3 and len(flagged_methods) >= 2 and is_multi_modal:
        level: Literal["low", "medium", "high", "inconclusive"] = "high"
        summary = (
            f"Strong multi-modal manipulation signals detected across {len(flagged_methods)} "
            f"independent methods ({', '.join(sorted(flagged_methods))})."
        )
        reasoning = (
            f"Level 'high' was assigned because {len(real_flagged)} findings from {len(flagged_methods)} "
            "independent methods corroborated manipulation across multiple modalities. "
            "Exculpatory original raw camera captures or verified cryptographic provenance "
            "would be required to alter this assessment."
        )
        return Overall(
            level=level,
            summary=summary,
            reasoning=reasoning,
            supporting_findings=supporting_ids,
            caveats=caveats,
        )

    # 5. Check for 'medium' level
    # 2 independent flagged methods, or 1 "high" finding supported by another.
    if len(flagged_methods) >= 2 or (has_high_conf_finding and len(real_flagged) >= 2):
        level = "medium"
        summary = (
            f"Multiple indicators flagged across {len(flagged_methods)} independent method(s): "
            f"{', '.join(sorted(flagged_methods))}."
        )
        reasoning = (
            f"Level 'medium' was selected because {len(flagged_methods)} independent forensic method(s) "
            f"flagged anomalous indicators ({', '.join(sorted(flagged_methods))}). Image-only evidence "
            "is capped below 'high'. Agreement with additional modalities (such as audio synthesis or "
            "cross-modal contradictions) would elevate this assessment to 'high', while confirmed benign "
            "recompression history would reduce it."
        )
        return Overall(
            level=level,
            summary=summary,
            reasoning=reasoning,
            supporting_findings=supporting_ids,
            caveats=caveats,
        )

    # 6. Check for 'low' level
    # A single flagged finding or only weak signals, or no findings flagged (clean).
    if len(real_flagged) >= 1:
        level = "low"
        summary = (
            f"Weak or isolated anomaly indicator detected ({', '.join(sorted(flagged_methods))})."
        )
        reasoning = (
            "Level 'low' was assigned because only a single method flagged an anomaly or signals were weak. "
            "An isolated signal does not demonstrate intentional manipulation on its own. "
            "Additional corroborating signals from an independent forensic analyzer or cross-modal "
            "inconsistency would change this level to 'medium' or 'high'."
        )
        return Overall(
            level=level,
            summary=summary,
            reasoning=reasoning,
            supporting_findings=supporting_ids,
            caveats=caveats,
        )

    # If nothing was flagged (clean analysis)
    level = "low"
    summary = "No anomalous manipulation indicators were flagged by active analyzers."
    reasoning = (
        "Level 'low' was selected because all executed non-stub analyzers returned clear findings with "
        "no anomalous indicators. Discovery of conflicting metadata, deepfake facial artifacts, or "
        "synthetic speech signals from future analyzer stages would change this level."
    )
    return Overall(
        level=level,
        summary=summary,
        reasoning=reasoning,
        supporting_findings=[],
        caveats=caveats,
    )
