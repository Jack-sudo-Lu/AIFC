import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from uuid import uuid4
from typing import Optional
from models import InputObject, Claim, CheckResponse, VerificationResult, Evidence
from services.extraction import extract_claims
from services.evidence_pipeline import gather_evidence
from services.evidence_store import add_document, collection, retrieve_evidence
from services.verifier import verify_claim
from services.scraper import scrape_url
from services.logger import log_event
from services.database import init_db, close_db, save_check, save_feedback, get_history, get_check_detail
from services.alignment import align_claim_evidence
from services.confidence import calibrate_confidence
from services.language import detect_language


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Global exception handler ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# --- Request models ---

class ClaimInput(BaseModel):
    claim_id: str
    claim_text: str

class RetrieveRequest(BaseModel):
    claim_id: str
    claim_text: str

class FeedbackRequest(BaseModel):
    trace_id: str
    claim_id: str
    claim_text: str
    original_status: str
    corrected_status: str
    note: Optional[str] = None

class EvidenceInput(BaseModel):
    text: str
    source: str


# --- Shared claim processing logic ---

async def process_claim(claim: Claim, lang: str = "en") -> VerificationResult:
    """Process a single claim: gather evidence, rerank, verify, align, calibrate."""
    trace_id = str(uuid4())

    # Gather evidence
    try:
        evidence = await asyncio.wait_for(
            gather_evidence(claim.claim_text, top_k=5, lang=lang),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        print(f"[check] Evidence gathering timed out for: {claim.claim_text[:50]}")
        evidence = []

    # Verify
    try:
        result = await asyncio.wait_for(
            verify_claim(
                {"claim_id": str(claim.claim_id), "claim_text": claim.claim_text},
                evidence,
            ),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        print(f"[check] Verification timed out for: {claim.claim_text[:50]}")
        result = {
            "status": "NEI",
            "reasoning": "Verification timed out. Please try again.",
            "confidence_score": 0.0,
            "relevant_evidence_ids": [],
        }

    # Alignment (Phase 3)
    alignment = None
    try:
        alignment = await asyncio.wait_for(
            align_claim_evidence(claim.claim_text, evidence),
            timeout=15.0,
        )
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[check] Alignment failed for: {claim.claim_text[:50]}: {e}")

    # Confidence calibration (Phase 3)
    raw_confidence = result.get("confidence_score", 0.0)
    calibrated = calibrate_confidence(
        llm_confidence=raw_confidence,
        alignment_result=alignment,
        evidence_list=evidence,
        verification_status=result.get("status", "NEI"),
    )
    result["confidence_score"] = calibrated

    result["trace_id"] = trace_id
    log_event({
        "type": "verification", "trace_id": trace_id,
        "claim": {"claim_id": str(claim.claim_id), "claim_text": claim.claim_text},
        "result": result, "is_human_correction": False,
    })

    return VerificationResult(
        claim_id=str(claim.claim_id),
        trace_id=trace_id,
        status=result.get("status", "NEI"),
        reasoning=result.get("reasoning", ""),
        confidence_score=result.get("confidence_score", 0.0),
        decomposition=result.get("decomposition"),
        alignment=alignment,
        evidence_used=evidence,
        relevant_evidence_ids=result.get("relevant_evidence_ids", []),
    )


# --- Core unified endpoint ---

@app.post("/api/check")
async def check(input_obj: InputObject) -> CheckResponse:
    """
    Unified pipeline: text or URL -> extract claims -> gather evidence -> verify.
    All claims are processed in parallel.
    """
    check_id = str(uuid4())
    raw_text = input_obj.raw_text

    if input_obj.url and not raw_text.strip():
        try:
            scraped = await scrape_url(input_obj.url)
            raw_text = scraped["text"]
        except Exception as e:
            return CheckResponse(
                check_id=check_id,
                input_text="",
                input_url=input_obj.url,
                claims=[],
                results=[VerificationResult(
                    claim_id="error", trace_id=check_id,
                    status="NEI", reasoning=f"Failed to scrape URL: {e}",
                    confidence_score=0.0,
                )],
            )

    # Detect language (Phase 3)
    lang = detect_language(raw_text)

    claims = await extract_claims(raw_text)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[process_claim(c, lang=lang) for c in claims]),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        print("[check] Overall request timed out")
        results = [
            VerificationResult(
                claim_id=str(c.claim_id), trace_id=str(uuid4()),
                status="NEI", reasoning="Request timed out. Please try again.",
                confidence_score=0.0,
            )
            for c in claims
        ]

    response = CheckResponse(
        check_id=check_id,
        input_text=raw_text,
        input_url=input_obj.url,
        claims=claims,
        results=list(results),
    )

    # Save to database
    try:
        await save_check(check_id, raw_text, input_obj.url, claims, list(results))
    except Exception as e:
        print(f"[check] Failed to save to DB: {e}")

    return response


# --- SSE Streaming endpoint ---

@app.post("/api/check/stream")
async def check_stream(input_obj: InputObject):
    """SSE streaming version: yields events as each claim completes."""

    async def event_generator():
        try:
            check_id = str(uuid4())
            raw_text = input_obj.raw_text

            if input_obj.url and not raw_text.strip():
                try:
                    scraped = await scrape_url(input_obj.url)
                    raw_text = scraped["text"]
                except Exception as e:
                    yield {"event": "error", "data": json.dumps({"message": f"Failed to scrape URL: {e}"})}
                    return

            # Detect language
            lang = detect_language(raw_text)

            claims = await extract_claims(raw_text)

            # Send claims_extracted event
            yield {
                "event": "claims_extracted",
                "data": json.dumps({
                    "claims": [c.model_dump(mode="json") for c in claims],
                    "check_id": check_id,
                }),
            }

            all_results = []

            # Send claim_started for all claims
            for claim in claims:
                yield {
                    "event": "claim_started",
                    "data": json.dumps({"claim_id": str(claim.claim_id)}),
                }

            # Process claims in parallel, yield results as they complete
            tasks = [asyncio.create_task(process_claim(c, lang=lang)) for c in claims]
            claim_by_task = dict(zip(tasks, claims))

            for coro in asyncio.as_completed(tasks):
                try:
                    result = await asyncio.wait_for(coro, timeout=90.0)
                    all_results.append(result)
                    yield {
                        "event": "claim_result",
                        "data": json.dumps(result.model_dump(mode="json")),
                    }
                except Exception as e:
                    print(f"[stream] Claim processing error: {e}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": f"Claim processing error: {e}"}),
                    }

            # Save to database
            try:
                await save_check(check_id, raw_text, input_obj.url, claims, all_results)
            except Exception as e:
                print(f"[stream] Failed to save to DB: {e}")

            yield {
                "event": "done",
                "data": json.dumps({"check_id": check_id}),
            }

        except Exception as e:
            print(f"[stream] Generator error: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Server error: {e}"}),
            }

    return EventSourceResponse(event_generator())


# --- History endpoints ---

@app.get("/api/history")
async def history(limit: int = 20, offset: int = 0):
    return await get_history(limit=limit, offset=offset)


@app.get("/api/history/{check_id}")
async def history_detail(check_id: str):
    detail = await get_check_detail(check_id)
    if detail is None:
        return JSONResponse(status_code=404, content={"detail": "Check not found"})
    return detail


# --- Legacy endpoints (kept for debugging) ---

@app.post("/api/extract", response_model=list[Claim])
async def extract(input_obj: InputObject) -> list[Claim]:
    raw_text = input_obj.raw_text
    if input_obj.url and not raw_text.strip():
        scraped = await scrape_url(input_obj.url)
        raw_text = scraped["text"]
    return await extract_claims(raw_text)

@app.post("/api/retrieve")
async def retrieve(req: RetrieveRequest):
    evidence = await gather_evidence(req.claim_text, top_k=3)
    return [e.model_dump() for e in evidence]

@app.post("/api/verify")
async def verify(claims: list[ClaimInput]):
    results = []
    for claim in claims:
        trace_id = str(uuid4())
        evidence = await gather_evidence(claim.claim_text, top_k=5)
        result = await verify_claim(claim.model_dump(), evidence)
        result["trace_id"] = trace_id
        log_event({
            "type": "verification", "trace_id": trace_id,
            "claim": claim.model_dump(), "result": result,
            "is_human_correction": False,
        })
        results.append(result)
    return results


# --- Feedback & evidence management ---

@app.post("/api/feedback")
async def feedback(req: FeedbackRequest):
    log_event({
        "type": "feedback", "trace_id": req.trace_id,
        "claim_id": req.claim_id, "claim_text": req.claim_text,
        "original_status": req.original_status,
        "corrected_status": req.corrected_status,
        "note": req.note, "is_human_correction": True,
    })

    # Save to SQLite
    try:
        await save_feedback(
            req.trace_id, req.claim_id, req.claim_text,
            req.original_status, req.corrected_status, req.note,
        )
    except Exception as e:
        print(f"[feedback] Failed to save to DB: {e}")

    # Knowledge base writeback (Phase 3): store corrected claim as gold standard
    if req.corrected_status != req.original_status:
        try:
            gold_text = f"[VERIFIED] {req.claim_text} — Status: {req.corrected_status}"
            if req.note:
                gold_text += f" — Note: {req.note}"
            add_document(gold_text, {
                "source": "human_feedback",
                "type": "gold_standard",
                "status": req.corrected_status,
                "claim_text": req.claim_text,
                "verified_date": __import__("datetime").datetime.now().isoformat(),
            })
        except Exception as e:
            print(f"[feedback] Failed to write gold standard: {e}")

    return {"status": "ok"}

@app.post("/api/evidence")
async def add_evidence(doc: EvidenceInput):
    add_document(doc.text, {"source": doc.source})
    return {"status": "ok", "total": collection.count()}

@app.get("/api/evidence/count")
async def evidence_count():
    return {"total": collection.count()}
