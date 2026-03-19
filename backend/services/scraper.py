import httpx
from urllib.parse import urlparse
from readability import Document
from bs4 import BeautifulSoup


async def scrape_url(url: str) -> dict:
    """
    Fetch a URL and extract clean article text.
    Returns:
    {
        "title": str,
        "text": str,
        "url": str,
        "domain": str,
    }
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AIFC/1.0; +https://github.com/aifc)",
            },
        )
        response.raise_for_status()

    doc = Document(response.text)
    soup = BeautifulSoup(doc.summary(), "html.parser")
    text = soup.get_text(separator="\n", strip=True)

    # Truncate to ~5000 chars to stay within LLM context
    if len(text) > 5000:
        text = text[:5000] + "..."

    return {
        "title": doc.title(),
        "text": text,
        "url": url,
        "domain": urlparse(url).netloc,
    }
