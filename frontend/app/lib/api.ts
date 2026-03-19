import { API_URL } from "./constants";
import type { CheckResponse, HistoryItem, HistoryDetail } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Server error: ${res.status}`);
  }
  return res.json();
}

export async function checkFacts(
  rawText: string,
  url?: string,
  signal?: AbortSignal
): Promise<CheckResponse> {
  return request<CheckResponse>("/api/check", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, url, source_platform: "web" }),
    signal,
  });
}

export function checkFactsStream(
  rawText: string,
  url?: string,
  signal?: AbortSignal
): ReadableStream<string> | Promise<Response> {
  return fetch(`${API_URL}/api/check/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText, url, source_platform: "web" }),
    signal,
  });
}

export async function submitFeedback(
  traceId: string,
  claimId: string,
  claimText: string,
  originalStatus: string,
  correctedStatus: string,
  note?: string
): Promise<void> {
  await request("/api/feedback", {
    method: "POST",
    body: JSON.stringify({
      trace_id: traceId,
      claim_id: claimId,
      claim_text: claimText,
      original_status: originalStatus,
      corrected_status: correctedStatus,
      note,
    }),
  });
}

export async function fetchHistory(
  limit = 20,
  offset = 0
): Promise<{ items: HistoryItem[]; total: number }> {
  return request(`/api/history?limit=${limit}&offset=${offset}`);
}

export async function fetchHistoryDetail(checkId: string): Promise<HistoryDetail> {
  return request(`/api/history/${checkId}`);
}
