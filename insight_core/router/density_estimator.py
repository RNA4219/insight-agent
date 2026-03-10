"""Evidence density estimator.

Estimates the evidence density based on extracted items.
"""

from __future__ import annotations

from insight_core.schemas import (
    ClaimItem,
    EvidenceDensity,
    EvidenceRef,
    LimitationItem,
)


def estimate_evidence_density(
    claims: list[ClaimItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
) -> EvidenceDensity:
    """Estimate evidence density from extracted items.

    Args:
        claims: Extracted claims.
        limitations: Extracted limitations.
        evidence_refs: Evidence references.

    Returns:
        Estimated evidence density (low/medium/high).
    """
    # Base scores
    claim_count = len(claims)
    limitation_count = len(limitations)
    evidence_count = len(evidence_refs)

    # Average confidence
    claim_confidence = (
        sum(c.confidence for c in claims) / len(claims) if claims else 0.5
    )

    # Evidence-to-claim ratio
    evidence_ratio = evidence_count / max(claim_count, 1)

    # Density score calculation
    # - More claims = higher density
    # - More evidence = higher density
    # - Higher confidence = higher density
    # - More limitations = potentially lower density (gaps identified)
    density_score = (
        min(claim_count * 0.1, 0.3) +  # Up to 0.3 from claim count
        min(evidence_ratio * 0.2, 0.3) +  # Up to 0.3 from evidence ratio
        claim_confidence * 0.3 +  # Up to 0.3 from confidence
        max(0, 0.1 - limitation_count * 0.02)  # Penalty for limitations
    )

    if density_score < 0.35:
        return EvidenceDensity.LOW
    elif density_score < 0.6:
        return EvidenceDensity.MEDIUM
    else:
        return EvidenceDensity.HIGH


def estimate_evidence_density_simple(
    claims: list[ClaimItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
) -> EvidenceDensity:
    """Simple evidence density estimation.

    Uses simple thresholds based on counts.

    Args:
        claims: Extracted claims.
        limitations: Extracted limitations.
        evidence_refs: Evidence references.

    Returns:
        Estimated evidence density.
    """
    total_items = len(claims) + len(evidence_refs)

    if total_items <= 2:
        return EvidenceDensity.LOW
    elif total_items <= 5:
        return EvidenceDensity.MEDIUM
    else:
        return EvidenceDensity.HIGH