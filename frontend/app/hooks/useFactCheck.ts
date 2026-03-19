"use client";
import { useState, useRef, useCallback } from "react";
import type { Claim, Result } from "../lib/types";
import { API_URL } from "../lib/constants";
import { submitFeedback as apiFeedback } from "../lib/api";

type FactCheckState = {
  claims: Claim[];
  results: Record<string, Result>;
  loading: boolean;
  error: string | null;
  checkId: string | null;
};

export function useFactCheck() {
  const [state, setState] = useState<FactCheckState>({
    claims: [],
    results: {},
    loading: false,
    error: null,
    checkId: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setState({ claims: [], results: {}, loading: false, error: null, checkId: null });
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setState((s) => ({ ...s, loading: false }));
  }, []);

  const checkFacts = useCallback(async (rawText: string, url?: string) => {
    if (state.loading) return;

    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    setState({ claims: [], results: {}, loading: true, error: null, checkId: null });

    try {
      const res = await fetch(`${API_URL}/api/check/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText, url, source_platform: "web" }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Server error: ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      // Persist across chunks so split event/data lines are reassembled
      let eventType = "";
      let eventData = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, ""); // handle \r\n endings

          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            eventData = line.slice(5).trim();
          } else if (line === "") {
            // Empty line = end of event
            if (eventType && eventData) {
              try {
                const parsed = JSON.parse(eventData);

                if (eventType === "claims_extracted") {
                  setState((s) => ({
                    ...s,
                    claims: parsed.claims,
                    checkId: parsed.check_id,
                  }));
                } else if (eventType === "claim_result") {
                  setState((s) => ({
                    ...s,
                    results: { ...s.results, [parsed.claim_id]: parsed },
                  }));
                } else if (eventType === "done") {
                  setState((s) => ({ ...s, checkId: parsed.check_id }));
                } else if (eventType === "error") {
                  setState((s) => ({ ...s, error: parsed.message }));
                }
              } catch {
                console.warn("Failed to parse SSE event:", eventType, eventData);
              }
            }
            eventType = "";
            eventData = "";
          }
        }
      }
    } catch (e: any) {
      if (e.name === "AbortError") {
        setState((s) => ({
          ...s,
          error: "Request was cancelled or timed out. Please try again.",
        }));
      } else {
        setState((s) => ({
          ...s,
          error: e.message || "Failed to check facts. Is the server running?",
        }));
      }
    } finally {
      clearTimeout(timeoutId);
      abortRef.current = null;
      setState((s) => ({ ...s, loading: false }));
    }
  }, [state.loading]);

  const submitFeedback = useCallback(
    async (claim: Claim, correctedStatus: string, note: string) => {
      const result = state.results[claim.claim_id];
      if (!result) return;

      try {
        await apiFeedback(
          result.trace_id,
          claim.claim_id,
          claim.claim_text,
          result.status,
          correctedStatus,
          note
        );
      } catch {}

      setState((s) => ({
        ...s,
        results: {
          ...s.results,
          [claim.claim_id]: { ...result, status: correctedStatus },
        },
      }));
    },
    [state.results]
  );

  return {
    ...state,
    checkFacts,
    cancel,
    reset,
    submitFeedback,
  };
}
