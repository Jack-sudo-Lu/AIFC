import type { Evidence } from "../lib/types";
import EvidenceItem from "./EvidenceItem";

type EvidencePanelProps = {
  evidence: Evidence[];
};

export default function EvidencePanel({ evidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return (
      <div className="mt-3 text-sm text-gray-400">No evidence found.</div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      {evidence.map((e, i) => (
        <EvidenceItem key={e.evidence_id || i} evidence={e} index={i} />
      ))}
    </div>
  );
}
