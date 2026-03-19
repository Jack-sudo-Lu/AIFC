import type { Evidence } from "../lib/types";
import { getCredibilityBadge } from "../lib/constants";

type EvidenceItemProps = {
  evidence: Evidence;
  index: number;
};

export default function EvidenceItem({ evidence, index }: EvidenceItemProps) {
  const cred = getCredibilityBadge(evidence.credibility_score);

  return (
    <div className="bg-gray-50 p-3 rounded-lg border-l-4 border-indigo-500 text-sm">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-mono text-gray-400 text-xs">[E{index}]</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${cred.style}`}>
          {cred.label}
        </span>
        <span
          className={`px-2 py-0.5 rounded text-xs ${
            evidence.origin === "web"
              ? "bg-purple-100 text-purple-700"
              : "bg-gray-100 text-gray-600"
          }`}
        >
          {evidence.origin === "web" ? "Web" : "Local KB"}
        </span>
      </div>
      <p className="text-gray-700 mb-1">
        {evidence.text.length > 300
          ? evidence.text.slice(0, 300) + "..."
          : evidence.text}
      </p>
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <span>{evidence.source_name}</span>
        {evidence.source_url && (
          <a
            href={evidence.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-500 hover:underline truncate max-w-xs"
          >
            {evidence.source_domain || evidence.source_url}
          </a>
        )}
      </div>
    </div>
  );
}
