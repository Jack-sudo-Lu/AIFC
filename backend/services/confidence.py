from models import Evidence


def calibrate_confidence(
    llm_confidence: float,
    alignment_result: dict | None,
    evidence_list: list[Evidence],
    verification_status: str,
) -> float:
    """
    Replace raw LLM confidence with a weighted calibrated score.

    calibrated = 0.20 * llm_confidence
               + 0.25 * evidence_coverage     (how many slots confirmed)
               + 0.25 * alignment_score        (from slot alignment)
               + 0.15 * source_agreement       (do multiple sources agree)
               + 0.15 * avg_credibility        (average source tier)
    """
    # Evidence coverage from alignment slots
    evidence_coverage = 0.0
    alignment_score = 0.0
    if alignment_result and alignment_result.get("slots"):
        slots = alignment_result["slots"]
        confirmed = sum(1 for s in slots if s.get("match") == "confirmed")
        total = len(slots)
        evidence_coverage = confirmed / total if total > 0 else 0.0
        alignment_score = alignment_result.get("alignment_score", 0.0)

    # Source agreement: do multiple sources agree on the verdict?
    source_agreement = 0.0
    if evidence_list:
        # Count distinct source domains
        domains = set()
        for e in evidence_list:
            d = e.source_domain or e.source_name
            if d:
                domains.add(d)
        n_sources = len(domains)
        # More independent sources = higher agreement
        if n_sources >= 3:
            source_agreement = 1.0
        elif n_sources == 2:
            source_agreement = 0.7
        elif n_sources == 1:
            source_agreement = 0.4
        else:
            source_agreement = 0.0

    # Average credibility
    avg_credibility = 0.0
    if evidence_list:
        avg_credibility = sum(e.credibility_score for e in evidence_list) / len(evidence_list)

    # Weighted combination
    calibrated = (
        0.20 * llm_confidence
        + 0.25 * evidence_coverage
        + 0.25 * alignment_score
        + 0.15 * source_agreement
        + 0.15 * avg_credibility
    )

    # NEI should generally have lower confidence
    if verification_status == "NEI" and calibrated > 0.5:
        calibrated = min(calibrated, 0.45)

    return max(0.0, min(1.0, round(calibrated, 3)))
