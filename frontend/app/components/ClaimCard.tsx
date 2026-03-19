"use client";
import { useState } from "react";
import type { Claim, Result } from "../lib/types";
import { MATCH_STYLES } from "../lib/constants";
import StatusBadge from "./StatusBadge";
import ConfidenceBar from "./ConfidenceBar";
import EvidencePanel from "./EvidencePanel";
import FeedbackPanel from "./FeedbackPanel";

type ClaimCardProps = {
  claim: Claim;
  result?: Result;
  onFeedback: (claim: Claim, correctedStatus: string, note: string) => void;
  readOnly?: boolean;
};

export default function ClaimCard({ claim, result, onFeedback, readOnly = false }: ClaimCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [decompExpanded, setDecompExpanded] = useState(false);
  const [alignmentExpanded, setAlignmentExpanded] = useState(false);
  const [editing, setEditing] = useState(false);

  const evidence = result?.evidence_used || [];

  const quickFeedback = (isCorrect: boolean) => {
    if (!result) return;
    onFeedback(
      claim,
      isCorrect ? result.status : "NEI",
      isCorrect ? "User confirmed" : "User disagreed"
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <p className="text-gray-800 font-medium">{claim.claim_text}</p>
          {claim.claim_type && claim.claim_type !== "other" && (
            <span className="text-xs text-gray-400 mt-1 inline-block">{claim.claim_type}</span>
          )}
        </div>
        {result && <StatusBadge status={result.status} />}
      </div>

      {result ? (
        <>
          <ConfidenceBar score={result.confidence_score} />
          <p className="text-gray-600 text-sm mb-3">{result.reasoning}</p>

          {/* Decomposition */}
          {result.decomposition && result.decomposition.length > 0 && (
            <div className="mb-3">
              <button
                onClick={() => setDecompExpanded(!decompExpanded)}
                className="text-indigo-600 text-xs font-medium"
              >
                {decompExpanded ? "Hide" : "Show"} Analysis Breakdown
              </button>
              {decompExpanded && (
                <div className="mt-2 space-y-1">
                  {result.decomposition.map((d, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className={`font-mono ${MATCH_STYLES[d.match] || "text-gray-500"}`}>
                        {d.match === "confirmed" ? "+" : d.match === "contradicted" ? "x" : "?"}
                      </span>
                      <span className="text-gray-700 font-medium">{d.component}</span>
                      {d.evidence_ref && <span className="text-gray-400">{d.evidence_ref}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Slot Alignment (Phase 3) */}
          {result.alignment && result.alignment.slots && result.alignment.slots.length > 0 && (
            <div className="mb-3">
              <button
                onClick={() => setAlignmentExpanded(!alignmentExpanded)}
                className="text-indigo-600 text-xs font-medium"
              >
                {alignmentExpanded ? "Hide" : "Show"} Slot Alignment ({Math.round(result.alignment.alignment_score * 100)}% match)
              </button>
              {alignmentExpanded && (
                <div className="mt-2 overflow-x-auto">
                  <table className="text-xs w-full border-collapse">
                    <thead>
                      <tr className="text-left text-gray-500">
                        <th className="pr-3 pb-1">Slot</th>
                        <th className="pr-3 pb-1">Claim</th>
                        <th className="pr-3 pb-1">Evidence</th>
                        <th className="pr-3 pb-1">Ref</th>
                        <th className="pb-1">Match</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.alignment.slots.map((slot, i) => (
                        <tr key={i} className="border-t border-gray-100">
                          <td className="pr-3 py-1 font-medium text-gray-700">{slot.name}</td>
                          <td className="pr-3 py-1 text-gray-600">{slot.claim_value}</td>
                          <td className="pr-3 py-1 text-gray-600">{slot.evidence_value}</td>
                          <td className="pr-3 py-1 text-gray-400">{slot.evidence_ref}</td>
                          <td className="py-1">
                            <span className={`font-mono ${MATCH_STYLES[slot.match] || "text-gray-500"}`}>
                              {slot.match === "confirmed" ? "+" : slot.match === "contradicted" ? "x" : "?"}
                              {" "}{slot.match}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Action buttons */}
          {!readOnly && (
            <div className="flex items-center gap-3 mb-3">
              <button onClick={() => quickFeedback(true)} className="text-green-600 hover:bg-green-50 px-2 py-1 rounded text-sm">
                Correct
              </button>
              <button onClick={() => quickFeedback(false)} className="text-red-600 hover:bg-red-50 px-2 py-1 rounded text-sm">
                Wrong
              </button>
              <button
                onClick={() => setEditing(!editing)}
                className="text-indigo-600 text-sm font-medium"
              >
                Edit
              </button>
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-indigo-600 text-sm font-medium ml-auto"
              >
                {expanded ? "Hide" : "Show"} Evidence ({evidence.length})
              </button>
            </div>
          )}

          {/* Read-only evidence toggle */}
          {readOnly && (
            <div className="flex items-center gap-3 mb-3">
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-indigo-600 text-sm font-medium"
              >
                {expanded ? "Hide" : "Show"} Evidence ({evidence.length})
              </button>
            </div>
          )}

          {/* Feedback form */}
          {editing && !readOnly && (
            <FeedbackPanel
              claim={claim}
              result={result}
              onSubmit={(correctedStatus, note) => {
                onFeedback(claim, correctedStatus, note);
                setEditing(false);
              }}
              onClose={() => setEditing(false)}
            />
          )}

          {/* Evidence */}
          {expanded && <EvidencePanel evidence={evidence} />}
        </>
      ) : (
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <div className="w-4 h-4 border-2 border-gray-300 border-t-indigo-500 rounded-full animate-spin" />
          Verifying...
        </div>
      )}
    </div>
  );
}
