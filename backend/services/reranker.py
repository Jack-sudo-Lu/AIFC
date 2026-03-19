import os
from sentence_transformers import CrossEncoder

_reranker = None
_reranker_multilingual = None


def _get_reranker(multilingual: bool = False) -> CrossEncoder:
    global _reranker, _reranker_multilingual
    if multilingual:
        if _reranker_multilingual is None:
            model_name = os.getenv(
                "RERANKER_MODEL_MULTILINGUAL",
                "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            )
            _reranker_multilingual = CrossEncoder(model_name)
        return _reranker_multilingual
    else:
        if _reranker is None:
            model_name = os.getenv(
                "RERANKER_MODEL",
                "cross-encoder/ms-marco-MiniLM-L-12-v2",
            )
            _reranker = CrossEncoder(model_name)
        return _reranker


def rerank_evidence(claim_text: str, evidence_list: list, lang: str = "en") -> list:
    """
    Re-score and re-sort evidence using a cross-encoder reranker.
    Each evidence item must have .text and .credibility_score attributes.
    Returns the same list re-sorted by combined reranker score.
    """
    if not evidence_list:
        return evidence_list

    is_multilingual = lang.startswith("zh")
    reranker = _get_reranker(multilingual=is_multilingual)

    # Create (claim, evidence_text) pairs for the cross-encoder
    pairs = [(claim_text, e.text) for e in evidence_list]

    # Score all pairs
    scores = reranker.predict(pairs)

    # Normalize scores to 0-1 range (cross-encoder scores can vary)
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score if max_score > min_score else 1.0

    for i, evidence in enumerate(evidence_list):
        normalized_relevance = (scores[i] - min_score) / score_range
        # Reranker-weighted combined score: relevance 0.7, credibility 0.3
        evidence.relevance_score = float(normalized_relevance)
        evidence.combined_score = float(normalized_relevance * 0.7 + evidence.credibility_score * 0.3)

    evidence_list.sort(key=lambda e: e.combined_score, reverse=True)
    return evidence_list
