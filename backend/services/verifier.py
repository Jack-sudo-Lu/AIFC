from services.llm import chat_json
from prompts.verification import VERIFICATION_SYSTEM
from models import Evidence


async def verify_claim(claim: dict, evidence_list: list[Evidence]) -> dict:
    """Verify a claim against evidence using structured LLM reasoning."""
    evidence_text = "\n".join([
        f"[E{i}] (Source: {e.source_name}, Credibility: {e.credibility_score:.1f}) {e.text}"
        for i, e in enumerate(evidence_list)
    ])

    user_msg = f"Claim: {claim['claim_text']}\n\nEvidence:\n{evidence_text}"

    try:
        result = await chat_json(
            system=VERIFICATION_SYSTEM,
            user=user_msg,
        )
    except Exception as e:
        print(f"[verifier] Error: {e}")
        result = {
            "status": "NEI",
            "reasoning": f"Verification failed: {str(e)}",
            "confidence_score": 0.0,
            "relevant_evidence_ids": [],
            "decomposition": [],
        }

    result["claim_id"] = claim.get("claim_id")
    return result
