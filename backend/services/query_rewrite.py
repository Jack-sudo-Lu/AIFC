from services.llm import chat_json
from prompts.query_rewrite import QUERY_REWRITE_SYSTEM


async def rewrite_claim_to_queries(claim_text: str, lang: str = "en") -> list[str]:
    """
    Given a claim, produce 2-3 optimized search queries.
    For Chinese claims, generates bilingual queries.
    Falls back to the original claim text on error.
    """
    # Augment system prompt with language hint
    system = QUERY_REWRITE_SYSTEM
    if lang.startswith("zh"):
        system += "\n\nIMPORTANT: This claim is in Chinese. You MUST generate queries in BOTH Chinese AND English. Return up to 4 queries."

    try:
        result = await chat_json(
            system=system,
            user=f"Claim: {claim_text}",
        )
        queries = result.get("queries", [])
        if isinstance(queries, list) and len(queries) > 0:
            return queries[:4]
    except Exception:
        pass
    return [claim_text]
