// All shared TypeScript types for the AIFC frontend

export type Claim = {
  claim_id: string;
  claim_text: string;
  subject: string;
  is_checkable: boolean;
  claim_type?: string;
};

export type Evidence = {
  evidence_id: string;
  text: string;
  source_url?: string;
  source_name: string;
  source_domain?: string;
  credibility_score: number;
  origin: string;
};

export type Decomposition = {
  component: string;
  evidence_ref: string;
  evidence_value?: string;
  match: string;
};

export type SlotAlignment = {
  name: string;
  claim_value: string;
  evidence_ref: string;
  evidence_value: string;
  match: "confirmed" | "contradicted" | "missing";
};

export type AlignmentResult = {
  slots: SlotAlignment[];
  alignment_score: number;
};

export type Result = {
  claim_id: string;
  trace_id: string;
  status: string;
  reasoning: string;
  confidence_score: number;
  decomposition?: Decomposition[];
  alignment?: AlignmentResult;
  evidence_used: Evidence[];
  relevant_evidence_ids: number[];
  error?: string;
};

export type CheckResponse = {
  check_id: string;
  input_text: string;
  input_url?: string;
  claims: Claim[];
  results: Result[];
};

export type HistoryItem = {
  id: string;
  input_text: string;
  input_url?: string;
  created_at: string;
  claim_count: number;
  supported_count: number;
  refuted_count: number;
  nei_count: number;
};

export type HistoryDetail = {
  id: string;
  input_text: string;
  input_url?: string;
  created_at: string;
  claims: Claim[];
  results: Result[];
};

// SSE event types
export type SSEEvent =
  | { type: "claims_extracted"; claims: Claim[] }
  | { type: "claim_started"; claim_id: string }
  | { type: "claim_result"; result: Result }
  | { type: "done"; check_id: string }
  | { type: "error"; message: string };
