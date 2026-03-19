import os
from urllib.parse import urlparse
from tavily import AsyncTavilyClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_tavily_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _client


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web using Tavily and return structured results.
    Has a 15-second timeout per query.
    """
    import asyncio

    client = get_tavily_client()
    try:
        response = await asyncio.wait_for(
            client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False,
            ),
            timeout=15.0,
        )
        return [_normalize_result(r) for r in response.get("results", [])]
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[web_search] Failed for query '{query[:50]}': {e}")
        return []


async def search_web_multiple(queries: list[str], max_per_query: int = 3) -> list[dict]:
    """Run multiple search queries and merge results, deduplicating by URL. 20s overall timeout."""
    import asyncio

    tasks = [search_web(q, max_results=max_per_query) for q in queries]
    try:
        all_results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        print("[web_search] Overall search timed out")
        return []

    seen_urls = set()
    merged = []
    for result_set in all_results:
        if isinstance(result_set, Exception):
            continue
        for r in result_set:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                merged.append(r)
    return merged


def _normalize_result(result: dict) -> dict:
    url = result.get("url", "")
    domain = urlparse(url).netloc if url else ""
    return {
        "title": result.get("title", ""),
        "url": url,
        "content": result.get("content", ""),
        "score": result.get("score", 0.0),
        "published_date": result.get("published_date"),
        "source_domain": domain,
    }
