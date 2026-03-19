# AIFC Phase 2: Complete Walkthrough

## What Changed: The Big Picture

Before Phase 2, the system worked but felt **slow and disposable** — you waited 30+ seconds staring at a blank screen, results vanished on refresh, and the entire UI was crammed into a single 357-line file. Now results **stream in one-by-one**, past checks are **saved and browsable**, and anyone can view a **shareable report URL**.

### Before (Phase 1)
```
User submits → waits 30s staring at blank screen → ALL results appear at once → refresh = gone
```

### After (Phase 2)
```
User submits → claims appear instantly → results stream in one-by-one as they complete
             → results saved to SQLite → browsable history sidebar
             → shareable report URL: /report/{check_id}
```

The frontend went from **1 file** to **19 files** — each component, hook, and utility is independently testable and reusable.

---

## New Files Created

### 1. `backend/services/database.py` — SQLite Persistence

**Problem it solves:** Every fact-check result was lost on page refresh. There was no way to see previous checks or learn from past corrections.

**What it does:**
- Uses `aiosqlite` (async SQLite) — no external database server needed
- Creates the database file at `backend/aifc.db`
- Auto-initializes tables on startup via FastAPI's `lifespan` context manager

**Three tables:**

```sql
checks (id, input_text, input_url, created_at)
    ↓ one-to-many
claim_results (id, check_id, claim_text, subject, claim_type,
               status, reasoning, confidence_score,
               evidence_json, decomposition_json, alignment_json,
               trace_id, created_at)
    ↓ one-to-many
feedback (id, claim_result_id, trace_id, claim_id, claim_text,
          original_status, corrected_status, note, created_at)
```

**Key functions:**

```python
async def save_check(check_id, input_text, input_url, claims, results)
    # Saves the entire check + all claim results in one transaction

async def save_feedback(trace_id, claim_id, claim_text, original_status, corrected_status, note)
    # Saves feedback AND updates the claim_result status in the DB

async def get_history(limit=20, offset=0) -> dict
    # Returns paginated list with aggregated counts (supported/refuted/NEI per check)

async def get_check_detail(check_id) -> dict | None
    # Returns full check with all claims, results, evidence, decomposition, alignment
```

**Why SQLite?** It's zero-config (no Docker, no server), supports async via `aiosqlite`, and handles the expected load (hundreds of checks/day) easily. WAL journal mode enables concurrent reads during writes.

---

### 2. `frontend/app/lib/types.ts` — Shared Type Definitions

**Problem it solves:** All types were inline in `page.tsx`. Components couldn't import them, and duplicating types across files would cause drift.

**What it contains:**

```typescript
Claim, Evidence, Decomposition, Result, CheckResponse    // existing types, extracted
SlotAlignment, AlignmentResult                             // new Phase 3 types
HistoryItem, HistoryDetail                                 // history types
SSEEvent                                                   // SSE streaming event union type
```

The `SSEEvent` type is a discriminated union — each event has a `type` field that TypeScript uses to narrow the payload:

```typescript
export type SSEEvent =
  | { type: "claims_extracted"; claims: Claim[] }
  | { type: "claim_started"; claim_id: string }
  | { type: "claim_result"; result: Result }
  | { type: "done"; check_id: string }
  | { type: "error"; message: string };
```

---

### 3. `frontend/app/lib/constants.ts` — Shared Constants

**Problem it solves:** Badge styles and credibility tiers were hardcoded inside `page.tsx`. Components like `StatusBadge` and `EvidenceItem` need the same styles.

**What it contains:**
- `STATUS_BADGE_STYLES` — maps `SUPPORTED`/`REFUTED`/`NEI` to Tailwind classes
- `MATCH_STYLES` — maps `confirmed`/`contradicted`/`missing` to text colors
- `getCredibilityBadge(score)` — returns `{label, style}` for Official/Trusted/Mainstream/General/Low
- `API_URL` — reads from `NEXT_PUBLIC_API_URL` env var, defaults to `http://localhost:8000`

---

### 4. `frontend/app/lib/api.ts` — API Client

**Problem it solves:** Fetch calls were inline in `page.tsx` with hardcoded URLs, no error handling, and no reuse.

**What it provides:**

```typescript
checkFacts(rawText, url?, signal?)     // POST /api/check (non-streaming fallback)
checkFactsStream(rawText, url?, signal?) // POST /api/check/stream (SSE)
submitFeedback(traceId, claimId, ...)   // POST /api/feedback
fetchHistory(limit?, offset?)           // GET /api/history
fetchHistoryDetail(checkId)             // GET /api/history/{id}
```

The internal `request<T>()` helper handles JSON parsing, error extraction from response body, and type-safe returns.

---

### 5. `frontend/app/hooks/useFactCheck.ts` — SSE Streaming Hook

**Problem it solves:** The old `checkFacts()` function waited for ALL claims to finish (`await fetch(...).then(res => res.json())`) before showing anything. For 3+ claims this meant 30+ seconds of blank screen.

**What it does:**
- Sends a POST to `/api/check/stream`
- Reads the SSE stream chunk-by-chunk using `ReadableStream`
- Updates React state incrementally as each event arrives
- Manages loading/error/cancel states

**SSE parsing logic (the tricky part):**

SSE events look like this on the wire:
```
event: claims_extracted\r\n
data: {"claims": [...]}\r\n
\r\n
event: claim_result\r\n
data: {"claim_id": "...", "status": "SUPPORTED", ...}\r\n
\r\n
```

The parser must handle:
1. **Chunked delivery** — `event:` and `data:` lines may arrive in different chunks. The `eventType` and `eventData` variables persist across chunks.
2. **`\r\n` line endings** — SSE spec uses `\r\n`, but `split("\n")` leaves trailing `\r`. Each line is stripped with `.replace(/\r$/, "")`.
3. **Empty line = event boundary** — when we see an empty line with both `eventType` and `eventData` set, we parse and dispatch the event.

**State shape:**
```typescript
{
  claims: Claim[],              // populated by claims_extracted
  results: Record<string, Result>, // populated incrementally by claim_result events
  loading: boolean,
  error: string | null,
  checkId: string | null,       // populated by done event
}
```

**User sees:** Claims appear immediately after extraction (~2s). Then each claim card transitions from skeleton to real result as it completes (~5-15s each, streaming in).

---

### 6. `frontend/app/hooks/useHistory.ts` — History Management Hook

**What it does:**
- Fetches paginated history from `GET /api/history`
- Provides `refresh()` (reload from start) and `loadMore()` (append next page)
- Auto-loads on mount

---

### 7. `frontend/app/components/InputPanel.tsx` — Input Section

**Extracted from:** `page.tsx` lines 141-189

**Props:** `text`, `url`, `inputMode`, `loading`, `onTextChange`, `onUrlChange`, `onModeChange`, `onSubmit`, `onCancel`

**Contains:** Text/URL tab switcher, textarea (text mode) or input field (URL mode), Check Facts button, Cancel button (shown only while loading).

---

### 8. `frontend/app/components/ClaimCard.tsx` — Single Claim Result

**Extracted from:** `page.tsx` lines 210-345 (the biggest chunk)

**This is the most complex component.** Each claim card manages its own local state for:
- `expanded` — show/hide evidence panel
- `decompExpanded` — show/hide analysis breakdown
- `alignmentExpanded` — show/hide slot alignment table (Phase 3)
- `editing` — show/hide feedback form

**Props:**
```typescript
{
  claim: Claim,
  result?: Result,         // undefined = still loading, show skeleton
  onFeedback: (claim, correctedStatus, note) => void,
  readOnly?: boolean,      // true on report page (no edit/feedback)
}
```

**New in Phase 2:** The `readOnly` prop. The report page (`/report/[id]`) renders claim cards without feedback buttons — viewers can see evidence but can't edit verdicts.

---

### 9. `frontend/app/components/ClaimCardSkeleton.tsx` — Loading Skeleton

**Problem it solves:** While claims are being processed, the UI showed a tiny "Verifying..." spinner. Now it shows a proper skeleton card with animated pulse effect, matching the real card's layout.

---

### 10. `frontend/app/components/EvidencePanel.tsx` + `EvidenceItem.tsx`

**Extracted from:** `page.tsx` lines 310-335

**Split into two components:** `EvidencePanel` renders the list, `EvidenceItem` renders a single evidence block with credibility badge, origin badge, truncated text, and source link.

---

### 11. `frontend/app/components/FeedbackPanel.tsx` — Correction Form

**Extracted from:** `page.tsx` lines 288-307

**Standalone component** with its own local state for status dropdown and note input. Calls `onSubmit(correctedStatus, note)` and `onClose()`.

---

### 12. `frontend/app/components/StatusBadge.tsx` + `ConfidenceBar.tsx`

Small pure components extracted for reuse. `StatusBadge` renders the SUPPORTED/REFUTED/NEI pill. `ConfidenceBar` renders the visual meter with color coding (green/yellow/red).

---

### 13. `frontend/app/components/ResultsSummary.tsx`

**Extracted from:** `page.tsx` lines 194-199

Shows: "Found 3 claims — 2 supported, 1 refuted, 0 insufficient evidence"

---

### 14. `frontend/app/components/ErrorBanner.tsx`

**New.** Displays error messages with Retry and Dismiss buttons. Used both in the main page and the report page.

---

### 15. `frontend/app/components/HistorySidebar.tsx`

**New.** A slide-in sidebar showing past fact checks.

**Features:**
- Toggle button (clock icon) fixed in the top-left corner
- Slides in from the left with CSS transform transition
- Each history item shows: truncated input text, date, status counts (2S 1R 0N)
- Selected item is highlighted with indigo border
- "Load more" button for pagination
- Main content shifts right when sidebar is open

---

### 16. `frontend/app/report/[id]/page.tsx` — Shareable Report Page

**Problem it solves:** Users couldn't share fact-check results. Copy-pasting text doesn't preserve the evidence chain.

**What it does:**
- Dynamic route: `/report/{check_id}`
- Fetches from `GET /api/history/{check_id}`
- Renders all claim cards in `readOnly` mode (no feedback buttons)
- Shows the original input text and timestamp
- Link back to the main fact checker

**Use case:** After checking facts, copy the URL (e.g., `localhost:3000/report/abc-123`), send it to a colleague — they see the same results with all evidence.

---

## Files Modified

### 17. `backend/main.py` — Major Expansion

**New: `POST /api/check/stream`** — SSE streaming endpoint:
```
1. Extract claims
2. Yield claims_extracted event (frontend shows claim cards immediately)
3. Yield claim_started for each claim
4. Process claims in parallel (asyncio.as_completed)
5. Yield claim_result as each one finishes (frontend updates that card)
6. Save to SQLite
7. Yield done event with check_id
```

The entire generator is wrapped in `try/except` — if anything crashes, the frontend gets an `error` event instead of a silent stream close.

**New: `GET /api/history`** — paginated history list with aggregated status counts.

**New: `GET /api/history/{check_id}`** — full check detail for the report page.

**Modified: `POST /api/check`** — now saves results to SQLite after processing.

**Modified: `POST /api/feedback`** — now saves to SQLite in addition to JSONL.

**New: Global exception handler** — catches unhandled exceptions and returns structured JSON:
```json
{"detail": "error message", "type": "ValueError"}
```

**New: `lifespan` context manager** — initializes SQLite on startup, closes on shutdown.

---

### 18. `frontend/app/page.tsx` — Rewritten (357 → ~70 lines)

**Before:** All types, state, logic, UI, styles in one file.

**After:** A slim orchestrator that:
1. Manages input state (`text`, `url`, `inputMode`)
2. Calls `useFactCheck()` for the streaming pipeline
3. Calls `useHistory()` for the sidebar
4. Renders components: `HistorySidebar`, `InputPanel`, `ErrorBanner`, `ResultsSummary`, `ClaimCard`/`ClaimCardSkeleton`

**No business logic remains in `page.tsx`** — it's purely composition.

---

### 19. `frontend/app/layout.tsx` — Minor Update

Added `overflow-x-hidden` to the body to prevent horizontal scrollbar when the sidebar slides in.

---

### 20. `backend/requirements.txt` — New Dependencies

| Package | Purpose |
|---------|---------|
| `aiosqlite` | Async SQLite for result persistence |
| `sse-starlette` | Server-Sent Events for streaming responses |

---

## How SSE Streaming Works (End to End)

Here's exactly what happens when a user types "Water boils at 100°C. The Great Wall is 5000 km long." and clicks Check Facts:

```
1. Frontend POSTs to /api/check/stream

2. Backend creates event_generator(), returns EventSourceResponse

3. Backend extracts claims: ["Water boils at 100°C", "The Great Wall is 5000 km long"]
   → Yields SSE event:
     event: claims_extracted
     data: {"claims": [...], "check_id": "abc-123"}

4. Frontend receives claims_extracted
   → Immediately renders two ClaimCardSkeletons (animated pulse)
   → User sees the claims appear after ~2 seconds

5. Backend starts processing both claims IN PARALLEL
   → Yields: event: claim_started for each claim

6. Claim 1 finishes first (simpler claim, faster evidence)
   → Yields:
     event: claim_result
     data: {"claim_id": "...", "status": "SUPPORTED", "confidence_score": 0.85, ...}

7. Frontend receives claim_result
   → Skeleton for claim 1 transitions to real ClaimCard
   → Claim 2 is still showing skeleton (still processing)

8. Claim 2 finishes
   → Yields another claim_result event
   → Frontend updates claim 2's skeleton to real ClaimCard

9. Backend saves everything to SQLite
   → Yields: event: done {"check_id": "abc-123"}

10. Frontend sets loading=false
    → History sidebar can now show this check
    → Report URL available at /report/abc-123
```

**Total perceived wait:** ~2s for claims to appear, then each result streams in as it completes. Even if one claim takes 20s, the other is visible at 8s. This feels dramatically faster than waiting 30s for both.

---

## Architecture After Phase 2

```
frontend/app/
  page.tsx                    ← slim orchestrator
  layout.tsx                  ← global layout + overflow fix
  globals.css                 ← Tailwind + gradient background
  lib/
    types.ts                  ← all TypeScript types
    constants.ts              ← badge styles, API URL
    api.ts                    ← API client functions
  hooks/
    useFactCheck.ts           ← SSE streaming hook
    useHistory.ts             ← history pagination hook
  components/
    InputPanel.tsx            ← text/URL tabs + submit
    ClaimCard.tsx             ← single claim with evidence, feedback, alignment
    ClaimCardSkeleton.tsx     ← loading skeleton
    EvidencePanel.tsx         ← evidence list
    EvidenceItem.tsx          ← single evidence with badges
    FeedbackPanel.tsx         ← correction form
    StatusBadge.tsx           ← SUPPORTED/REFUTED/NEI pill
    ConfidenceBar.tsx         ← visual confidence meter
    ResultsSummary.tsx        ← claim count summary
    ErrorBanner.tsx           ← error display with retry
    HistorySidebar.tsx        ← past checks sidebar
  report/[id]/
    page.tsx                  ← shareable read-only report

backend/
  main.py                     ← +SSE endpoint, +history endpoints, +DB saves, +error handler
  models.py                   ← +alignment field on VerificationResult
  services/
    database.py               ← NEW: SQLite persistence
    (all other services unchanged)
```
