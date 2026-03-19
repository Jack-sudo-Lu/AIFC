import os
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=30.0)
    return _client


def get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def chat_json(system: str, user: str, model: str = None) -> dict:
    """Send a chat message expecting JSON response. 30s timeout."""
    client = get_client()
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model or get_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        ),
        timeout=30.0,
    )
    return json.loads(response.choices[0].message.content)
