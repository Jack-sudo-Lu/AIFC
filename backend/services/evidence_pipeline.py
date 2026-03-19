import asyncio
from uuid import uuid4
from models import Evidence
from services.query_rewrite import rewrite_claim_to_queries
from services.web_search import search_web_multiple
from services.evidence_store import retrieve_evidence as chromadb_retrieve
from services.credibility import score_source_credibility


async def gather_evidence(claim_text: str, top_k: int = 5, lang: str = "en") -> list[Evidence]:
    """
    Hybrid evidence pipeline:
    1. Rewrite claim into search queries (with language awareness)
    2. Execute web search + ChromaDB search in parallel
    3. Merge, deduplicate, score credibility
    4. Rerank with cross-encoder (Phase 3)
    5. Return top_k ranked results
    """
    queries = await rewrite_claim_to_queries(claim_text, lang=lang)

    web_task = search_web_multiple(queries, max_per_query=3)
    local_task = asyncio.to_thread(chromadb_retrieve, claim_text, top_k=3)

    web_results, local_results = await asyncio.gather(
        web_task, local_task, return_exceptions=True
    )

    evidence_list = []

    # Process web results
    if isinstance(web_results, list):
        for r in web_results:
            cred = score_source_credibility(r.get("url", ""))
            rel = r.get("score", 0.5)
            evidence_list.append(Evidence(
                evidence_id=str(uuid4()),
                text=r["content"],
                source_url=r.get("url"),
                source_name=r.get("title", "Web source"),
                source_domain=r.get("source_domain"),
                published_date=r.get("published_date"),
                relevance_score=rel,
                credibility_score=cred,
                combined_score=rel * 0.6 + cred * 0.4,
                origin="web",
            ))

    # Process local ChromaDB results
    if isinstance(local_results, list):
        for r in local_results:
            meta = r.get("metadata", {})
            # Gold standard entries (Phase 3) get a credibility boost
            is_gold = meta.get("type") == "gold_standard"
            cred = 0.95 if is_gold else 0.7
            rel = 0.8 if is_gold else 0.5

            evidence_list.append(Evidence(
                evidence_id=str(uuid4()),
                text=r["text"],
                source_name=meta.get("source", "Local KB"),
                relevance_score=rel,
                credibility_score=cred,
                combined_score=rel * 0.6 + cred * 0.4,
                origin="local",
            ))

    # Rerank with cross-encoder (Phase 3) — optional, falls back gracefully
    try:
        from services.reranker import rerank_evidence
        evidence_list = await asyncio.to_thread(
            rerank_evidence, claim_text, evidence_list, lang
        )
    except ImportError:
        # sentence-transformers not installed, skip reranking
        evidence_list.sort(key=lambda e: e.combined_score, reverse=True)
    except Exception as e:
        print(f"[evidence_pipeline] Reranker failed, using default scoring: {e}")
        evidence_list.sort(key=lambda e: e.combined_score, reverse=True)

    return evidence_list[:top_k]
