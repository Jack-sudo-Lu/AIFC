# AIFC Phase 1: Complete Walkthrough

## What Changed: The Big Picture

Before Phase 1, the system had **5 hardcoded facts** and could only verify claims against those 5 facts. Now it searches the **real internet** for evidence, uses **better prompts**, and processes claims **in parallel**.

### Before (V0)
```
User text → Extract claims (GPT-4o-mini) → Search 5 local facts (ChromaDB) → Verify (GPT-4o-mini) → Show result
```

### After (Phase 1)
```
User text or URL → Extract claims (better prompt) → For each claim IN PARALLEL:
  → Rewrite into search queries (LLM)
  → Search the internet (Tavily) + Search local KB (ChromaDB)
  → Score source credibility
  → Verify with structured reasoning (better prompt)
→ Show results with evidence sources, credibility badges, and claim decomposition
```

---

## New Files Created

### 1. `backend/services/llm.py` — Centralized LLM Client

**Problem it solves:** Before, `extraction.py` and `verifier.py` each created their own `OpenAI()` client with hardcoded `"gpt-4o-mini"`. If you wanted to switch models, you'd edit 3 files.

**What it does:**
- Creates a single `AsyncOpenAI` client (async = non-blocking, allows parallel requests)
- Reads model name from `OPENAI_MODEL` env var (defaults to `gpt-4o-mini`)
- Provides a `chat_json()` helper that sends a system+user message and parses the JSON response

**Key function:**
```python
async def chat_json(system: str, user: str) -> dict
```
Every service that talks to OpenAI now calls this instead of managing its own client.

---

### 2. `backend/prompts/extraction.py` — Claim Extraction Prompt

**Problem it solves:** The old prompt was 4 lines:
```
Extract factual claims from this text. Return JSON array only.
```
It didn't distinguish opinions from facts, didn't handle Chinese, and didn't categorize claims.

**What the new prompt does:**
- Defines what a "checkable claim" is (must have specific subject + verifiable predicate)
- Tells the LLM to preserve original language (important for Chinese claims)
- Extracts a `claim_type` field: `statistical`, `event`, `attribution`, `comparative`, `definition`, `other`
- Limits to 5 claims max, prioritizing the most specific ones
- Explicitly tells the LLM to skip vague statements like "many people think..."

---

### 3. `backend/prompts/verification.py` — Verification Prompt

**Problem it solves:** The old prompt was:
```
Compare this claim against the evidence and return JSON only.
```
The LLM would sometimes use its own knowledge (hallucination), return REFUTED when evidence was simply absent, and give confidence scores of 1.0 for everything.

**What the new prompt does:**
- Forces a 4-step reasoning process: Decompose → Map → Check → Verdict
- Requires `[E0]`, `[E1]` citation anchoring — the LLM must point to specific evidence
- Defines confidence score guidelines (0.9+ = multiple authoritative sources, 0.3 = limited evidence)
- Critical rule: **absence of evidence = NEI, NOT REFUTED**
- Returns a `decomposition` array showing which parts of the claim were confirmed/contradicted/missing

**Example decomposition output:**
```json
{
  "decomposition": [
    {"component": "Water boils at 100°C", "evidence_ref": "[E0]", "match": "confirmed"},
    {"component": "at sea level", "evidence_ref": "[E0]", "match": "confirmed"}
  ]
}
```

---

### 4. `backend/prompts/query_rewrite.py` — Query Rewrite Prompt

**Problem it solves:** The old `generate_search_query()` was literally:
```python
def generate_search_query(claim_text: str) -> str:
    return claim_text  # did nothing
```
Passing a full claim sentence as a search query gives poor results.

**What the new prompt does:**
- Generates exactly 3 search queries per claim:
  1. **Query 1:** Targets the primary authoritative source (government, official report)
  2. **Query 2:** Targets the specific data point or statistic
  3. **Query 3:** Broader context query for alternative sources
- For Chinese claims, generates queries in BOTH Chinese and English
- Strips opinion words, keeps only verifiable facts

**Example:**
```
Claim: "China's GDP grew 5.2% in 2025 according to NBS"
→ Query 1: "National Bureau of Statistics China GDP 2025 official"
→ Query 2: "China GDP growth rate 5.2% 2025"
→ Query 3: "China economic growth 2025 statistics"
```

---

### 5. `backend/services/web_search.py` — Tavily Web Search

**Problem it solves:** The system had NO way to search the internet. It could only look up 5 hardcoded facts.

**What it does:**
- Calls the Tavily API with `search_depth="advanced"` which returns **full article text** (not just snippets)
- `search_web(query)` — single query search, returns up to 5 results
- `search_web_multiple(queries)` — runs multiple queries in parallel, deduplicates by URL
- Each result contains: `title`, `url`, `content` (full text), `score` (relevance), `source_domain`

**Why Tavily?** Unlike Google Custom Search which returns 2-line snippets, Tavily extracts and returns the actual article content. This is critical because the verifier LLM needs real text to reason about, not just titles.

---

### 6. `backend/services/query_rewrite.py` — Query Rewrite Service

**What it does:**
- Takes a claim text, sends it to the LLM with the query rewrite prompt
- Returns 2-4 optimized search queries
- If the LLM call fails, falls back to using the original claim text (graceful degradation)

---

### 7. `backend/services/scraper.py` — URL Article Extraction

**Problem it solves:** Users couldn't paste a URL to fact-check an article.

**What it does:**
- Fetches the URL with `httpx` (async HTTP client)
- Uses `readability-lxml` to extract the main article content (strips navigation, ads, sidebars)
- Uses `BeautifulSoup` to convert HTML to clean text
- Truncates to 5000 chars to stay within LLM context limits
- Returns: `title`, `text`, `url`, `domain`

**How it's used:** When a user submits a URL instead of text, `main.py` calls `scrape_url()` first, then feeds the scraped text into the extraction pipeline.

---

### 8. `backend/services/credibility.py` — Source Credibility Scoring

**Problem it solves:** A random blog post was treated the same as a `.gov` source. The system had no concept of source quality.

**What it does:** Scores any URL from 0.0 to 1.0 based on domain authority:

| Tier | Score | Examples |
|------|-------|---------|
| Tier 1 | 0.95 | `.gov`, `.edu`, `reuters.com`, `who.int`, `stats.gov.cn` |
| Tier 2 | 0.80 | `bbc.com`, `nytimes.com`, `nature.com`, `xinhua.net`, `wikipedia.org` |
| Tier 3 | 0.60 | `cnn.com`, `bloomberg.com`, `statista.com` |
| Default | 0.40 | Unknown domains |
| Low | 0.20 | `reddit.com`, `blogspot`, `medium.com`, `zhihu.com` |

This score is displayed in the frontend as credibility badges (Official / Trusted / Mainstream / General / Low).

---

### 9. `backend/services/evidence_pipeline.py` — The Orchestrator

**This is the core of Phase 1.** It replaces the old direct ChromaDB query with a full evidence-gathering pipeline.

**Step-by-step flow:**

```
1. Receive claim text
2. Call query_rewrite → get 3 search queries
3. IN PARALLEL:
   a. search_web_multiple(queries) → web results
   b. chromadb_retrieve(claim_text) → local KB results
4. For each web result:
   - Score credibility based on domain
   - Calculate combined_score = relevance × 0.6 + credibility × 0.4
5. For each local KB result:
   - Assign default scores (credibility 0.7 since they're curated)
6. Sort all evidence by combined_score descending
7. Return top 5
```

**Why both web + local?** Web search finds real-time evidence. Local ChromaDB stores curated "gold standard" facts and human-verified corrections (future Phase 3 feature). They complement each other.

---

## Files Modified

### 10. `backend/models.py` — Expanded Data Models

**Added 3 new models:**

**`Evidence`** — represents a single piece of evidence:
```
evidence_id, text, source_url, source_name, source_domain,
published_date, relevance_score, credibility_score, combined_score,
origin ("web" or "local")
```

**`VerificationResult`** — the full verification output:
```
claim_id, trace_id, status, reasoning, confidence_score,
decomposition (structured breakdown), evidence_used (list of Evidence),
relevant_evidence_ids
```

**`CheckResponse`** — the unified `/api/check` response:
```
check_id, input_text, input_url, claims, results
```

Also fixed `InputObject` — the old version called `uuid4()` and `datetime.now()` at class definition time (a Python bug where all instances share the same ID). Now uses `model_post_init` to generate per-instance values.

---

### 11. `backend/services/extraction.py` — Upgraded

**Changes:**
- Uses `llm.chat_json()` instead of creating its own OpenAI client
- Uses the new extraction prompt from `prompts/extraction.py`
- Now `async` (was synchronous)
- Extracts `claim_type` field
- Still falls back to wrapping raw text as a single claim on error, but now logs the error

---

### 12. `backend/services/verifier.py` — Upgraded

**Changes:**
- Uses `llm.chat_json()` instead of creating its own OpenAI client
- Uses the new verification prompt from `prompts/verification.py`
- Now `async`
- Accepts `list[Evidence]` objects instead of raw dicts
- Passes source credibility info to the LLM in the evidence text:
  ```
  [E0] (Source: NASA, Credibility: 0.95) The Earth is 93 million miles...
  ```
- Returns structured `decomposition` showing per-component analysis

---

### 13. `backend/services/evidence_store.py` — Cleaned Up

**Changes:**
- Removed the `generate_search_query()` stub (now lives in `query_rewrite.py`)
- Kept as the local ChromaDB store only
- Still auto-seeds 5 facts on first run
- Still provides `add_document()` and `retrieve_evidence()` for the evidence pipeline

---

### 14. `backend/main.py` — Major Rewrite

**New endpoint: `POST /api/check`** — the unified pipeline:
1. If URL provided → scrape it
2. Extract claims from text
3. For each claim **in parallel** (`asyncio.gather`):
   - Gather evidence (web + local)
   - Verify against evidence
   - Log the result
4. Return complete `CheckResponse`

**All endpoints are now `async`** — this means multiple claims process concurrently instead of one-by-one.

**Legacy endpoints kept** (`/api/extract`, `/api/retrieve`, `/api/verify`) — they still work but now use the new pipeline internally. The frontend calls `/api/check` only.

---

### 15. `frontend/app/page.tsx` — Updated UI

**New features:**
- **Text/URL tab switcher** — users can paste text OR a URL
- **Uses `/api/check`** — single API call instead of multiple sequential calls
- **Error handling** — try/catch with error banner display
- **Result summary** — "Found 3 claims — 2 supported, 1 refuted, 0 insufficient evidence"
- **Credibility badges** on each evidence item (Official / Trusted / Mainstream / General / Low)
- **Origin badges** — "Web" (purple) or "Local KB" (gray) for each evidence piece
- **Source links** — clickable URLs to original evidence sources
- **Claim decomposition** — expandable "Analysis Breakdown" showing per-component verification
- **Confidence bar colors** — green (≥70%), yellow (40-69%), red (<40%)
- **Evidence text truncation** — long evidence snippets are cut to 300 chars with "..."

---

## New Dependencies

| Package | Purpose |
|---------|---------|
| `tavily-python` | Web search API |
| `httpx` | Async HTTP client for URL scraping |
| `readability-lxml` | Article content extraction from HTML |
| `beautifulsoup4` | HTML to text conversion |
| `lxml` | HTML parser (required by readability) |

---

## New Environment Variables

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `TAVILY_API_KEY` | Tavily web search API key | Yes (for web search) |
| `OPENAI_MODEL` | LLM model name | No (defaults to `gpt-4o-mini`) |

---

## How a Request Flows (End to End)

Here's exactly what happens when a user types "The Earth is 93 million miles from the Sun" and clicks Check Facts:

```
1. Frontend POSTs to /api/check with {raw_text: "...", source_platform: "web"}

2. main.py receives it, generates a check_id

3. Calls extract_claims("The Earth is 93 million miles from the Sun")
   → llm.py sends to GPT-4o-mini with extraction prompt
   → Returns: [{claim_text: "The Earth is 93 million miles from the Sun",
                 subject: "Earth", claim_type: "statistical", is_checkable: true}]

4. For the claim, calls gather_evidence() which:

   4a. Calls rewrite_claim_to_queries()
       → llm.py sends to GPT-4o-mini with query rewrite prompt
       → Returns: ["Earth Sun distance 93 million miles NASA",
                    "Earth average distance Sun miles kilometers",
                    "astronomical unit Earth Sun distance"]

   4b. IN PARALLEL:
       - search_web_multiple() → Tavily searches all 3 queries → ~9 web results, deduplicated to ~6
       - chromadb_retrieve() → searches local KB → 3 results

   4c. Scores credibility for each web result:
       - nasa.gov → 0.95
       - caltech.edu → 0.95
       - random blog → 0.40

   4d. Calculates combined_score = relevance × 0.6 + credibility × 0.4

   4e. Sorts and returns top 5

5. Calls verify_claim() with the claim + 5 evidence pieces
   → llm.py sends to GPT-4o-mini with verification prompt
   → LLM decomposes claim: ["Earth", "93 million miles", "from the Sun"]
   → Maps each component to evidence: [E0] NASA confirms, [E1] NASA confirms...
   → Returns: {status: "SUPPORTED", confidence: 0.95, decomposition: [...]}

6. Logs the full trace to logs.jsonl

7. Returns CheckResponse to frontend

8. Frontend displays the claim card with:
   - Green "SUPPORTED" badge
   - 95% confidence bar (green)
   - Reasoning with [E0], [E1] citations
   - Expandable evidence list with credibility badges and source links
   - Expandable analysis breakdown
```
