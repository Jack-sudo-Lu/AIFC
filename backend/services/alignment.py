from services.llm import chat_json
from prompts.alignment import ALIGNMENT_SYSTEM
from models import Evidence


async def align_claim_evidence(claim_text: str, evidence_list: list[Evidence]) -> dict | None:
    """
    Run slot alignment between a claim and its evidence.
    Returns {slots: [...], alignment_score: float} or None on failure.
    """
    if not evidence_list:
        return None

    evidence_text = "\n".join([
        f"[E{i}] (Source: {e.source_name}) {e.text}"
        for i, e in enumerate(evidence_list)
    ])

    user_msg = f"Claim: {claim_text}\n\nEvidence:\n{evidence_text}"

    try:
        result = await chat_json(
            system=ALIGNMENT_SYSTEM,
            user=user_msg,
        )
        slots = result.get("slots", [])
        alignment_score = result.get("alignment_score", 0.0)

        # Validate and clamp alignment_score
        if not isinstance(alignment_score, (int, float)):
            alignment_score = 0.0
        alignment_score = max(0.0, min(1.0, alignment_score))

        return {
            "slots": slots,
            "alignment_score": alignment_score,
        }
    except Exception as e:
        print(f"[alignment] Error: {e}")
        return None
