"use client";
import type { HistoryItem } from "../lib/types";

type HistorySidebarProps = {
  items: HistoryItem[];
  loading: boolean;
  selectedId?: string;
  onSelect: (id: string) => void;
  onLoadMore?: () => void;
  hasMore: boolean;
  isOpen: boolean;
  onToggle: () => void;
};

export default function HistorySidebar({
  items, loading, selectedId, onSelect, onLoadMore, hasMore, isOpen, onToggle,
}: HistorySidebarProps) {
  return (
    <>
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="fixed top-4 left-4 z-50 bg-white/90 backdrop-blur rounded-lg shadow-lg p-2 hover:bg-white transition"
        title={isOpen ? "Close history" : "Open history"}
      >
        <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          )}
        </svg>
      </button>

      {/* Sidebar panel */}
      <div
        className={`fixed top-0 left-0 h-full w-72 bg-white/95 backdrop-blur shadow-2xl z-40 transform transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-4 pt-14">
          <h2 className="text-lg font-bold text-gray-800 mb-4">History</h2>

          {loading && items.length === 0 && (
            <div className="text-gray-400 text-sm">Loading...</div>
          )}

          <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-120px)]">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`w-full text-left p-3 rounded-lg text-sm transition ${
                  selectedId === item.id
                    ? "bg-indigo-50 border border-indigo-200"
                    : "hover:bg-gray-50 border border-transparent"
                }`}
              >
                <div className="text-gray-800 font-medium line-clamp-2 mb-1">
                  {item.input_text
                    ? item.input_text.slice(0, 80) + (item.input_text.length > 80 ? "..." : "")
                    : item.input_url || "Unknown input"}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  <span className="text-green-600">{item.supported_count}S</span>
                  <span className="text-red-600">{item.refuted_count}R</span>
                  <span className="text-yellow-600">{item.nei_count}N</span>
                </div>
              </button>
            ))}
          </div>

          {hasMore && onLoadMore && (
            <button
              onClick={onLoadMore}
              disabled={loading}
              className="w-full mt-3 text-center text-indigo-600 text-sm hover:underline disabled:opacity-50"
            >
              {loading ? "Loading..." : "Load more"}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
