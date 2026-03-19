# AIFC Phase 3: Complete Walkthrough

## What Changed: The Big Picture

Before Phase 3, the system found evidence and verified claims — but it wasn't **smart** about it. Evidence ranking was whatever Tavily's search API returned. Confidence scores were whatever the LLM felt like saying. Chinese claims only generated English search queries. Human corrections were logged but never used again.

Phase 3 adds **intelligence layers** on top of the existing pipeline:

### Before (Phase 2)
```
Claim → Search queries (English only) → Evidence (Tavily ranking) → Verify (raw LLM confidence) → Result
                                                                      ↓
                                                              Human correction → logged to JSONL (never used)
```

### After (Phase 3)
```
Claim → Detect language → Search queries (bilingual for Chinese)
      → Evidence (Tavily + ChromaDB) → Cross-encoder reranking → Verify
      → Slot alignment (which parts match which evidence?)
      → Calibrated confidence (multi-factor, not just LLM opinion)
      → Result with alignment table
                    ↓
      Human correction → written back to ChromaDB as gold standard
                       → boosts future retrievals for same claim
```

---

## New Files Created

### 1. `backend/services/language.py` — Language Detection

**Problem it solves:** A Chinese claim like "2023年中国GDP约为126万亿人民币" would get search queries like "China GDP 2023 official report" — all in English. The best evidence for Chinese claims is often on Chinese government sites (stats.gov.cn), Chinese news (xinhua.net), and requires Chinese search queries to find.

**What it does:**

```python
detect_language(text: str) -> str
    # Returns ISO 639-1 code: "zh-cn", "en", "fr", etc.
    # Uses langdetect library (Google's language detection algorithm)
    # Falls back to "en" for empty or undetectable text

is_chinese(lang: str) -> bool
    # Checks if lang starts with "zh"

get_search_languages(lang: str) -> list[str]
    # Chinese → ["zh", "en"] (search in both languages)
    # Everything else → [lang] (search in detected language only)
```

**Why both Chinese AND English?** Many official Chinese statistics are published in both languages. Searching in English finds international coverage (World Bank, IMF), while searching in Chinese finds primary sources (国家统计局, 新华社). The combination provides better evidence coverage.

---

### 2. `backend/services/reranker.py` — Cross-Encoder Evidence Reranking

**Problem it solves:** Evidence was ranked by Tavily's search API relevance score, which is based on keyword matching and page authority — NOT on how well the evidence actually answers the claim. A page about "GDP" would score high for a GDP claim even if it discusses a completely different country or year.

**What a cross-encoder does:** Unlike a bi-encoder (which embeds query and document separately), a cross-encoder processes the (claim, evidence) pair **together** through a transformer. This means it understands the relationship between the specific claim and the specific evidence passage.

**Example:**
```
Claim: "China's GDP grew 5.2% in 2023"

Evidence A: "According to NBS, China's GDP growth was 5.2% in 2023"
  → Cross-encoder score: 0.97 (directly confirms the claim)

Evidence B: "GDP growth across major economies in 2023 varied widely"
  → Tavily score: 0.85 (contains "GDP" and "2023")
  → Cross-encoder score: 0.31 (mentions GDP but not China's specific rate)
```

**Two models:**
- English claims: `cross-encoder/ms-marco-MiniLM-L-12-v2` (~33M params, fast)
- Chinese/multilingual claims: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (trained on multilingual data)

**Scoring formula:**
```python
combined_score = normalized_relevance * 0.7 + credibility * 0.3
```
Note: the weight shifted from Phase 1's `0.6/0.4` to `0.7/0.3`. This is because the cross-encoder's relevance score is much higher quality than Tavily's keyword-based score, so it deserves more weight.

**Score normalization:** Cross-encoder scores can range from -10 to +10 (not 0 to 1). The reranker normalizes them to 0-1 using min-max scaling across the batch.

**Graceful degradation:** The reranker requires `sentence-transformers` (which pulls in PyTorch — a large dependency). If it's not installed, `evidence_pipeline.py` catches the `ImportError` and falls back to the Phase 1 ranking:

```python
try:
    from services.reranker import rerank_evidence
    evidence_list = await asyncio.to_thread(rerank_evidence, claim_text, evidence_list, lang)
except ImportError:
    # sentence-transformers not installed, skip reranking
    evidence_list.sort(key=lambda e: e.combined_score, reverse=True)
except Exception as e:
    print(f"Reranker failed, using default scoring: {e}")
    evidence_list.sort(key=lambda e: e.combined_score, reverse=True)
```

---

### 3. `backend/services/alignment.py` — Claim-Evidence Slot Alignment

**Problem it solves:** The verifier says "SUPPORTED" and gives a reasoning paragraph, but doesn't show **exactly** which parts of the claim are confirmed by **exactly** which parts of the evidence. A user reading "SUPPORTED, confidence 0.85" has to trust the LLM's word. With slot alignment, they can see a table showing the mapping.

**What "slots" are:** A claim is decomposed into atomic verifiable components:

```
Claim: "China's GDP in 2023 was approximately 126 trillion yuan"

Slots:
  subject: "China"
  metric: "GDP"
  time_period: "2023"
  value: "approximately 126 trillion yuan"
```

**What alignment does:** For each slot, it finds the corresponding text span in the evidence and checks if they match:

```json
{
  "slots": [
    {
      "name": "subject",
      "claim_value": "China",
      "evidence_ref": "[E0]",
      "evidence_value": "China's national GDP",
      "match": "confirmed"
    },
    {
      "name": "value",
      "claim_value": "approximately 126 trillion yuan",
      "evidence_ref": "[E0]",
      "evidence_value": "126.06 trillion yuan",
      "match": "confirmed"
    }
  ],
  "alignment_score": 1.0
}
```

**alignment_score** = confirmed slots / total slots. This number feeds into the confidence calibration formula.

**The LLM prompt** (`prompts/alignment.py`) instructs the model to:
- Extract 2-6 slots per claim (don't over-decompose)
- Cite the most authoritative evidence for each slot
- Preserve original language in claim/evidence values
- Only mark "contradicted" when evidence **explicitly** states a different value

**Timeout:** Alignment runs with a 15-second timeout. If it times out, the result is `None` — the system still works, just without the alignment table.

---

### 4. `backend/prompts/alignment.py` — Alignment Prompt Template

**Defines the slot extraction and mapping instructions.** Key rules:

1. Common slot types: `subject`, `metric`, `value`, `time_period`, `attribution`, `location`, `comparison`
2. Extract 2-6 slots (simple claims get fewer)
3. `alignment_score = confirmed / total`
4. Cite the most authoritative evidence for each slot
5. Only "contradicted" when evidence **explicitly** states a different value

---

### 5. `backend/services/confidence.py` — Confidence Calibration

**Problem it solves:** LLM confidence scores are notoriously unreliable:
- Claim with 1 mediocre blog source → LLM says confidence 0.95
- Claim with 3 government sources → LLM says confidence 0.72
- Any NEI claim → LLM says confidence 0.5 (default guess)

The raw LLM confidence is basically the model's vibe, not a calibrated probability.

**The calibration formula:**

```
calibrated = 0.20 × llm_confidence
           + 0.25 × evidence_coverage     ← how many slots are confirmed
           + 0.25 × alignment_score        ← from slot alignment
           + 0.15 × source_agreement       ← do multiple independent sources agree
           + 0.15 × avg_credibility        ← average source quality tier
```

**Each factor explained:**

| Factor | Weight | What it measures | Range |
|--------|--------|-----------------|-------|
| `llm_confidence` | 20% | The LLM's raw confidence estimate | 0.0 - 1.0 |
| `evidence_coverage` | 25% | Fraction of slots confirmed by evidence | 0.0 - 1.0 |
| `alignment_score` | 25% | Overall slot alignment quality | 0.0 - 1.0 |
| `source_agreement` | 15% | How many independent sources agree | 0.0 - 1.0 |
| `avg_credibility` | 15% | Mean credibility of all evidence sources | 0.0 - 1.0 |

**Source agreement scoring:**
- 3+ distinct source domains → 1.0
- 2 distinct sources → 0.7
- 1 source → 0.4
- 0 sources → 0.0

**NEI cap:** If the verdict is NEI but the calibrated score is above 0.5, it's capped at 0.45. NEI means "not enough info" — a high confidence score for NEI is contradictory.

**Example calibration:**

```
Claim: "Water boils at 100°C at sea level"
LLM says confidence: 0.95

Calibration inputs:
  llm_confidence: 0.95
  evidence_coverage: 1.0 (all 2 slots confirmed)
  alignment_score: 1.0
  source_agreement: 1.0 (3 sources: physics textbook, NASA, Britannica)
  avg_credibility: 0.75

Calibrated = 0.20×0.95 + 0.25×1.0 + 0.25×1.0 + 0.15×1.0 + 0.15×0.75
           = 0.19 + 0.25 + 0.25 + 0.15 + 0.1125
           = 0.953

Result: Very similar to LLM's estimate (good evidence confirms it)
```

```
Claim: "The moon is made of cheese"
LLM says confidence: 0.90 (for REFUTED)

Calibration inputs:
  llm_confidence: 0.90
  evidence_coverage: 0.5 (only 1 of 2 slots has evidence)
  alignment_score: 0.5
  source_agreement: 0.4 (only 1 source)
  avg_credibility: 0.60

Calibrated = 0.20×0.90 + 0.25×0.5 + 0.25×0.5 + 0.15×0.4 + 0.15×0.60
           = 0.18 + 0.125 + 0.125 + 0.06 + 0.09
           = 0.58

Result: LLM was overconfident (0.90 → 0.58). Only 1 source, partial coverage.
```

---

## Files Modified

### 6. `backend/services/evidence_pipeline.py` — Reranking + Gold Standard Boost

**Three changes:**

**a) Language parameter:** Now accepts `lang` and passes it to `rewrite_claim_to_queries()`:
```python
async def gather_evidence(claim_text: str, top_k: int = 5, lang: str = "en")
    queries = await rewrite_claim_to_queries(claim_text, lang=lang)
```

**b) Gold standard boost:** When processing local ChromaDB results, entries with `type: "gold_standard"` metadata get higher scores:
```python
is_gold = meta.get("type") == "gold_standard"
cred = 0.95 if is_gold else 0.7   # gold standard = almost authoritative
rel = 0.8 if is_gold else 0.5     # gold standard = highly relevant
```

**c) Cross-encoder reranking:** After merging web + local results, runs the cross-encoder reranker (if available):
```python
try:
    from services.reranker import rerank_evidence
    evidence_list = await asyncio.to_thread(rerank_evidence, claim_text, evidence_list, lang)
except ImportError:
    evidence_list.sort(key=lambda e: e.combined_score, reverse=True)
```

The `asyncio.to_thread()` is important — the cross-encoder is a CPU-bound PyTorch model. Running it in a thread prevents it from blocking the async event loop.

---

### 7. `backend/services/query_rewrite.py` — Bilingual Query Generation

**Change:** Now accepts a `lang` parameter. For Chinese claims, appends an instruction to the system prompt:

```python
if lang.startswith("zh"):
    system += "\n\nIMPORTANT: This claim is in Chinese. You MUST generate queries in BOTH Chinese AND English. Return up to 4 queries."
```

**Example:**
```
Claim: "2023年中国GDP约为126万亿人民币"

Before (Phase 2): ["China GDP 2023 official", "China GDP growth rate", "China economic data"]
After (Phase 3):  ["中国GDP 2023 国家统计局", "2023年中国GDP 126万亿", "China GDP 2023 trillion yuan", "China economic growth 2023"]
```

The bilingual queries find evidence from both Chinese government sources (stats.gov.cn) and international sources (World Bank), giving the verifier a more complete evidence set.

---

### 8. `backend/main.py` — Pipeline Integration

**New in `process_claim()`:**

The `process_claim()` function (shared by both `/api/check` and `/api/check/stream`) now has three new steps after verification:

```python
# 1. Detect language (at the top, shared across claims)
lang = detect_language(raw_text)

# 2. Alignment (after verification)
alignment = await align_claim_evidence(claim.claim_text, evidence)

# 3. Confidence calibration (after alignment)
calibrated = calibrate_confidence(
    llm_confidence=raw_confidence,
    alignment_result=alignment,
    evidence_list=evidence,
    verification_status=result.get("status", "NEI"),
)
result["confidence_score"] = calibrated  # replaces raw LLM confidence
```

**New in `/api/feedback` — Knowledge Base Writeback:**

When a user corrects a verdict, the corrected claim is stored as a "gold standard" entry in ChromaDB:

```python
if req.corrected_status != req.original_status:
    gold_text = f"[VERIFIED] {req.claim_text} — Status: {req.corrected_status}"
    add_document(gold_text, {
        "source": "human_feedback",
        "type": "gold_standard",
        "status": req.corrected_status,
        "claim_text": req.claim_text,
        "verified_date": datetime.now().isoformat(),
    })
```

**What this means:** If a user corrects "China's GDP is 126 trillion yuan" from REFUTED to SUPPORTED, that correction gets stored in ChromaDB. Next time anyone checks a similar claim, the gold standard entry appears in the evidence (with boosted credibility 0.95), nudging the verifier toward the correct answer.

---

### 9. `backend/models.py` — Alignment Field

Added `alignment: Optional[dict] = None` to `VerificationResult`. This carries the slot alignment data from backend to frontend through the API response and SSE stream.

---

### 10. `frontend/app/components/ClaimCard.tsx` — Alignment Display

**New section:** Between the decomposition and the action buttons, the ClaimCard now renders a slot alignment table (when alignment data is present):

```
Show Slot Alignment (85% match)

| Slot         | Claim                     | Evidence                        | Ref  | Match      |
|--------------|---------------------------|---------------------------------|------|------------|
| subject      | China                     | China's national GDP             | [E0] | + confirmed |
| metric       | GDP                       | gross domestic product           | [E0] | + confirmed |
| time_period  | 2023                      | 2023                            | [E0] | + confirmed |
| value        | ~126 trillion yuan        | 126.06 trillion yuan            | [E0] | + confirmed |
```

The table uses the same green/red/gray color coding as the decomposition breakdown: `+` (green) for confirmed, `x` (red) for contradicted, `?` (gray) for missing.

---

### 11. `backend/requirements.txt` — New Dependencies

| Package | Purpose | Size Impact |
|---------|---------|-------------|
| `sentence-transformers` | Cross-encoder reranking model | Large (~500MB with PyTorch) |
| `langdetect` | Language detection | Small (~1MB) |

**Note:** `sentence-transformers` is optional. If not installed, the reranker is skipped and evidence uses the Phase 1 Tavily-based ranking. This keeps the system runnable on machines without GPUs or large disk space.

---

## How a Request Flows (End to End, Phase 3)

Here's exactly what happens when a user submits "2023年中国GDP约为126万亿人民币":

```
1. Frontend POSTs to /api/check/stream

2. Backend detects language:
   → langdetect("2023年中国GDP约为126万亿人民币") → "zh-cn"

3. Extracts claims:
   → [{claim_text: "2023年中国GDP约为126万亿人民币",
       subject: "中国GDP", claim_type: "statistical"}]

4. Yields claims_extracted SSE event → frontend shows skeleton card

5. process_claim() starts:

   5a. gather_evidence() with lang="zh-cn":
       → rewrite_claim_to_queries("...", lang="zh-cn")
       → LLM gets extra instruction: "generate queries in BOTH Chinese AND English"
       → Queries: ["中国GDP 2023 国家统计局", "2023年中国GDP 126万亿",
                    "China GDP 2023 trillion yuan"]

   5b. IN PARALLEL:
       - Tavily searches all 3 queries → web results from stats.gov.cn, xinhua, worldbank
       - ChromaDB retrieves → "Global GDP in 2023 was approximately $105 trillion"

   5c. Cross-encoder reranking (if available):
       → Uses multilingual model (mmarco-mMiniLMv2)
       → Re-scores each (claim, evidence) pair
       → stats.gov.cn article jumps to #1 (directly discusses Chinese GDP)
       → Generic global GDP article drops to #4

   5d. Returns top 5 evidence pieces

6. verify_claim() → LLM reasons with [E0]-[E4] citations
   → Returns: {status: "SUPPORTED", confidence: 0.92, decomposition: [...]}

7. align_claim_evidence():
   → LLM extracts slots: [subject: "中国", metric: "GDP", time: "2023", value: "126万亿"]
   → Maps each to evidence: all 4 confirmed by [E0]
   → Returns: {alignment_score: 1.0, slots: [...]}

8. calibrate_confidence():
   → llm_confidence: 0.92
   → evidence_coverage: 1.0 (4/4 slots confirmed)
   → alignment_score: 1.0
   → source_agreement: 1.0 (stats.gov.cn, xinhua, worldbank = 3 sources)
   → avg_credibility: 0.87 (mix of .gov.cn and major news)
   → calibrated = 0.20×0.92 + 0.25×1.0 + 0.25×1.0 + 0.15×1.0 + 0.15×0.87
                = 0.184 + 0.25 + 0.25 + 0.15 + 0.1305
                = 0.965

9. Yields claim_result SSE event
   → Frontend updates skeleton to real card
   → Shows: SUPPORTED, 97% confidence, slot alignment table

10. Saves to SQLite → yields done event
```

---

## The Feedback Loop (Knowledge Base Writeback)

Here's what happens when a user corrects a verdict:

```
1. User clicks "Wrong" on a REFUTED claim for "Earth has 206 bones"
   → Frontend calls POST /api/feedback with corrected_status: "SUPPORTED"

2. Backend:
   a. Logs to logs.jsonl (as before)
   b. Saves to SQLite feedback table
   c. Updates claim_result status in SQLite
   d. Writes to ChromaDB:
      text: "[VERIFIED] Earth has 206 bones — Status: SUPPORTED"
      metadata: {type: "gold_standard", status: "SUPPORTED", ...}

3. Next time someone checks "humans have 206 bones":
   a. ChromaDB retrieval finds the gold standard entry
   b. evidence_pipeline gives it credibility 0.95 (gold_standard boost)
   c. It appears in evidence with high ranking
   d. Verifier sees "[VERIFIED]" prefix + high credibility → more likely correct verdict

4. Over time, the system self-corrects for claims it initially got wrong
```

---

## The Intelligence Stack

Phase 3 adds four independent intelligence layers. Each one can fail gracefully without affecting the others:

```
Layer 1: Language Detection       → Better queries     (langdetect, always works)
Layer 2: Cross-Encoder Reranking  → Better evidence    (optional, needs PyTorch)
Layer 3: Slot Alignment           → Better explanation (LLM call, 15s timeout)
Layer 4: Confidence Calibration   → Better scores      (pure math, always works)
         + Knowledge Writeback    → Better over time   (ChromaDB, always works)
```

If PyTorch isn't installed → Layer 2 skips, everything else works.
If alignment times out → Layer 3 returns None, calibration uses 0 for alignment inputs.
If the LLM is slow → the system degrades to Phase 1 behavior (still correct, just less smart).

---

## Architecture After Phase 3

```
backend/services/
  language.py           ← NEW: language detection + bilingual query support
  reranker.py           ← NEW: cross-encoder evidence reranking
  alignment.py          ← NEW: claim-evidence slot alignment
  confidence.py         ← NEW: multi-factor confidence calibration
  evidence_pipeline.py  ← MODIFIED: +reranking, +gold standard boost, +lang param
  query_rewrite.py      ← MODIFIED: +bilingual query generation
  verifier.py           ← unchanged (calibration applied externally)
  llm.py                ← unchanged
  web_search.py         ← unchanged
  evidence_store.py     ← unchanged (writeback uses existing add_document)
  credibility.py        ← unchanged
  scraper.py            ← unchanged
  logger.py             ← unchanged
  database.py           ← unchanged

backend/prompts/
  alignment.py          ← NEW: slot extraction + mapping prompt
  extraction.py         ← unchanged
  verification.py       ← unchanged
  query_rewrite.py      ← unchanged

backend/main.py         ← MODIFIED: +alignment in pipeline, +writeback in feedback
backend/models.py       ← MODIFIED: +alignment field on VerificationResult
```

---

## Verification Checklist

Test these scenarios to verify Phase 3 is working:

1. **Bilingual queries:** Submit "2023年中国GDP约为126万亿人民币" → check backend logs for Chinese + English queries
2. **Reranking:** Submit a claim → evidence should have the most directly relevant source at position [E0] (not just the highest Tavily score)
3. **Slot alignment:** Expand a claim result → click "Show Slot Alignment" → see the table with confirmed/contradicted/missing slots
4. **Confidence calibration:** Compare scores — weak-evidence claims should score lower than strong-evidence claims, regardless of what the LLM "feels"
5. **Knowledge writeback:** Correct a verdict → re-submit the same claim → the gold standard entry should appear in the evidence list with "Local KB" badge
6. **Graceful degradation:** Uninstall `sentence-transformers` → submit a claim → should still work (reranker skipped, everything else runs)
