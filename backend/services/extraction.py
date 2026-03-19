from uuid import uuid4
from services.llm import chat_json
from prompts.extraction import EXTRACTION_SYSTEM
from models import Claim


async def extract_claims(raw_text: str) -> list[Claim]:
    """Extract verifiable factual claims from text using LLM."""
    try:
        data = await chat_json(
            system=EXTRACTION_SYSTEM,
            user=f"Text to analyze:\n\n{raw_text}",
        )
        claims_data = data.get("claims", data) if isinstance(data, dict) else data
        if isinstance(claims_data, dict):
            claims_data = [claims_data]

        return [
            Claim(
                claim_id=uuid4(),
                claim_text=c["claim_text"],
                subject=c.get("subject", ""),
                claim_date=c.get("claim_date"),
                is_checkable=c.get("is_checkable", True),
                claim_type=c.get("claim_type", "other"),
            )
            for c in claims_data
        ]
    except Exception as e:
        print(f"[extraction] Error: {e}")
        return [Claim(
            claim_id=uuid4(),
            claim_text=raw_text,
            subject="error",
            claim_date=None,
            is_checkable=True,
        )]
