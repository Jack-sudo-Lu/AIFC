"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import type { Claim, Result, HistoryDetail } from "../../lib/types";
import { fetchHistoryDetail } from "../../lib/api";
import ClaimCard from "../../components/ClaimCard";
import ResultsSummary from "../../components/ResultsSummary";
import ErrorBanner from "../../components/ErrorBanner";

export default function ReportPage() {
  const params = useParams();
  const id = params.id as string;

  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchHistoryDetail(id)
      .then(setDetail)
      .catch((e) => setError(e.message || "Report not found"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen p-6 flex items-center justify-center">
        <div className="text-white text-lg">Loading report...</div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="min-h-screen p-6">
        <div className="max-w-3xl mx-auto pt-20">
          <ErrorBanner message={error || "Report not found"} />
          <div className="text-center mt-6">
            <a href="/" className="text-white underline">Back to Fact Checker</a>
          </div>
        </div>
      </div>
    );
  }

  const resultMap: Record<string, Result> = {};
  for (const r of detail.results) {
    resultMap[r.claim_id] = r;
  }

  const supported = detail.results.filter((r) => r.status === "SUPPORTED").length;
  const refuted = detail.results.filter((r) => r.status === "REFUTED").length;
  const nei = detail.results.filter((r) => r.status === "NEI").length;

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-3xl mx-auto">
        <header className="text-center text-white mb-8 pt-8">
          <h1 className="text-4xl font-bold mb-2">Fact Check Report</h1>
          <p className="opacity-90">
            {new Date(detail.created_at).toLocaleString()}
          </p>
        </header>

        {/* Input context */}
        <div className="bg-white rounded-2xl shadow-2xl p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-500 mb-2 uppercase tracking-wide">
            Checked Text
          </h2>
          <p className="text-gray-700 text-sm whitespace-pre-wrap">
            {detail.input_text
              ? detail.input_text.slice(0, 500) + (detail.input_text.length > 500 ? "..." : "")
              : detail.input_url || "N/A"}
          </p>
          {detail.input_url && (
            <a
              href={detail.input_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-500 text-sm hover:underline mt-2 inline-block"
            >
              {detail.input_url}
            </a>
          )}
        </div>

        <div className="space-y-4">
          <ResultsSummary
            total={detail.claims.length}
            supported={supported}
            refuted={refuted}
            nei={nei}
          />

          {detail.claims.map((claim) => (
            <ClaimCard
              key={claim.claim_id}
              claim={claim}
              result={resultMap[claim.claim_id]}
              onFeedback={() => {}}
              readOnly
            />
          ))}
        </div>

        <footer className="text-center text-white mt-8 opacity-70">
          <p>
            <a href="/" className="underline">AI Fact Checker</a> &copy; 2026
          </p>
        </footer>
      </div>
    </div>
  );
}
