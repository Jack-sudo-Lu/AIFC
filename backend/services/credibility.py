from urllib.parse import urlparse

# Tier 1: Government, international orgs, wire services (0.95)
TIER_1_DOMAINS = {
    "reuters.com", "apnews.com", "who.int", "worldbank.org", "imf.org",
    "un.org", "nasa.gov", "cdc.gov", "nih.gov", "bls.gov", "census.gov",
    "stats.gov.cn", "mof.gov.cn", "pbc.gov.cn",
}

# Tier 1 TLD patterns
TIER_1_TLDS = {".gov", ".edu"}

# Tier 2: Major news, academic, authoritative media (0.80)
TIER_2_DOMAINS = {
    "bbc.com", "bbc.co.uk", "nytimes.com", "washingtonpost.com",
    "economist.com", "ft.com", "wsj.com", "theguardian.com",
    "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com", "arxiv.org",
    "xinhua.net", "xinhuanet.com", "people.com.cn", "chinadaily.com.cn",
    "wikipedia.org",
}

# Tier 3: Established media and reference sites (0.60)
TIER_3_DOMAINS = {
    "cnn.com", "cnbc.com", "bloomberg.com", "forbes.com",
    "abc.net.au", "aljazeera.com", "dw.com",
    "statista.com", "britannica.com", "investopedia.com",
    "sina.com.cn", "sohu.com", "163.com", "caixin.com",
}

# Low credibility patterns (0.20)
LOW_CREDIBILITY_PATTERNS = {
    "blogspot", "wordpress.com", "medium.com", "substack.com",
    "reddit.com", "quora.com", "facebook.com", "twitter.com", "x.com",
    "tiktok.com", "weibo.com", "zhihu.com",
}


def score_source_credibility(url: str) -> float:
    """Score a URL's source credibility from 0.0 to 1.0."""
    if not url:
        return 0.3

    domain = urlparse(url).netloc.lower()
    # Strip www. prefix
    if domain.startswith("www."):
        domain = domain[4:]

    # Check Tier 1 exact matches
    for t1 in TIER_1_DOMAINS:
        if domain == t1 or domain.endswith("." + t1):
            return 0.95

    # Check Tier 1 TLD patterns
    for tld in TIER_1_TLDS:
        if domain.endswith(tld) or f"{tld}." in domain:
            return 0.95

    # Check Tier 2
    for t2 in TIER_2_DOMAINS:
        if domain == t2 or domain.endswith("." + t2):
            return 0.80

    # Check Tier 3
    for t3 in TIER_3_DOMAINS:
        if domain == t3 or domain.endswith("." + t3):
            return 0.60

    # Check low credibility
    for pattern in LOW_CREDIBILITY_PATTERNS:
        if pattern in domain:
            return 0.20

    # Default for unknown domains
    return 0.40
