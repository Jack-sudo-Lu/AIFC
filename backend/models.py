from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, Literal


class InputObject(BaseModel):
    request_id: UUID = None
    raw_text: str = ""
    url: Optional[str] = None
    source_platform: str = "web"
    lang: str = "en"
    created_at: datetime = None

    def model_post_init(self, __context):
        if self.request_id is None:
            self.request_id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.now()


class Claim(BaseModel):
    claim_id: UUID
    claim_text: str
    subject: str
    claim_date: Optional[str] = None
    is_checkable: bool
    claim_type: str = "other"


class Evidence(BaseModel):
    evidence_id: str
    text: str
    source_url: Optional[str] = None
    source_name: str = "Unknown"
    source_domain: Optional[str] = None
    published_date: Optional[str] = None
    relevance_score: float = 0.0
    credibility_score: float = 0.5
    combined_score: float = 0.0
    origin: Literal["web", "local"] = "web"


class VerificationResult(BaseModel):
    claim_id: str
    trace_id: str
    status: Literal["SUPPORTED", "REFUTED", "NEI"]
    reasoning: str
    confidence_score: float
    decomposition: Optional[list[dict]] = None
    alignment: Optional[dict] = None
    evidence_used: list[Evidence] = []
    relevant_evidence_ids: list[int] = []


class CheckResponse(BaseModel):
    check_id: str
    input_text: str
    input_url: Optional[str] = None
    claims: list[Claim]
    results: list[VerificationResult]
