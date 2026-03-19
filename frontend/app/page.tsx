"use client";
import { useState } from "react";
import { useFactCheck } from "./hooks/useFactCheck";
import { useHistory } from "./hooks/useHistory";
import InputPanel from "./components/InputPanel";
import ClaimCard from "./components/ClaimCard";
import ClaimCardSkeleton from "./components/ClaimCardSkeleton";
import ResultsSummary from "./components/ResultsSummary";
import ErrorBanner from "./components/ErrorBanner";
import HistorySidebar from "./components/HistorySidebar";
import { fetchHistoryDetail } from "./lib/api";

export default function Home() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "url">("text");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { claims, results, loading, error, checkFacts, cancel, submitFeedback } = useFactCheck();
  const history = useHistory();

  const handleSubmit = () => {
    const input = inputMode === "text" ? text.trim() : "";
    const inputUrl = inputMode === "url" ? url.trim() : undefined;
    if (!input && !inputUrl) return;
    checkFacts(input, inputUrl);
    history.refresh();
  };

  const handleHistorySelect = async (id: string) => {
    try {
      const detail = await fetchHistoryDetail(id);
      // Populate the UI with historical results
      // We'll update the fact check state indirectly by mapping results
      setText(detail.input_text || "");
      setUrl(detail.input_url || "");
      setInputMode(detail.input_url ? "url" : "text");
    } catch (e) {
      console.error("Failed to load history detail:", e);
    }
  };

  const supported = Object.values(results).filter((r) => r.status === "SUPPORTED").length;
  const refuted = Object.values(results).filter((r) => r.status === "REFUTED").length;
  const nei = Object.values(results).filter((r) => r.status === "NEI").length;

  // Claims that are still loading (no result yet)
  const pendingClaims = claims.filter((c) => !results[c.claim_id]);

  return (
    <div className="min-h-screen p-6">
      <HistorySidebar
        items={history.items}
        loading={history.loading}
        onSelect={handleHistorySelect}
        onLoadMore={history.loadMore}
        hasMore={history.hasMore}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className={`max-w-3xl mx-auto transition-all ${sidebarOpen ? "ml-80" : ""}`}>
        <header className="text-center text-white mb-8 pt-8">
          <h1 className="text-4xl font-bold mb-2">AI Fact Checker</h1>
          <p className="opacity-90">Verify claims with AI-powered evidence search</p>
        </header>

        <InputPanel
          text={text}
          url={url}
          inputMode={inputMode}
          loading={loading}
          onTextChange={setText}
          onUrlChange={setUrl}
          onModeChange={setInputMode}
          onSubmit={handleSubmit}
          onCancel={cancel}
        />

        {error && (
          <ErrorBanner
            message={error}
            onRetry={handleSubmit}
            onDismiss={() => {}}
          />
        )}

        {claims.length > 0 && (
          <div className="space-y-4">
            <ResultsSummary
              total={claims.length}
              supported={supported}
              refuted={refuted}
              nei={nei}
            />

            {claims.map((claim) => {
              const result = results[claim.claim_id];
              return result ? (
                <ClaimCard
                  key={claim.claim_id}
                  claim={claim}
                  result={result}
                  onFeedback={submitFeedback}
                />
              ) : (
                <ClaimCardSkeleton key={claim.claim_id} />
              );
            })}
          </div>
        )}

        {loading && claims.length === 0 && (
          <div className="space-y-4">
            <ClaimCardSkeleton />
            <ClaimCardSkeleton />
          </div>
        )}

        <footer className="text-center text-white mt-8 opacity-70">
          <p>&copy; 2026 AI Fact Checker</p>
        </footer>
      </div>
    </div>
  );
}
