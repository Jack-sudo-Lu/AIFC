"use client";

type InputPanelProps = {
  text: string;
  url: string;
  inputMode: "text" | "url";
  loading: boolean;
  onTextChange: (v: string) => void;
  onUrlChange: (v: string) => void;
  onModeChange: (mode: "text" | "url") => void;
  onSubmit: () => void;
  onCancel: () => void;
};

export default function InputPanel({
  text, url, inputMode, loading,
  onTextChange, onUrlChange, onModeChange, onSubmit, onCancel,
}: InputPanelProps) {
  return (
    <div className="bg-white rounded-2xl shadow-2xl p-8 mb-6">
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => onModeChange("text")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
            inputMode === "text" ? "bg-indigo-100 text-indigo-700" : "text-gray-500 hover:bg-gray-100"
          }`}
        >
          Text
        </button>
        <button
          onClick={() => onModeChange("url")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
            inputMode === "url" ? "bg-indigo-100 text-indigo-700" : "text-gray-500 hover:bg-gray-100"
          }`}
        >
          URL
        </button>
      </div>

      {inputMode === "text" ? (
        <textarea
          className="w-full h-32 p-4 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-indigo-500 transition"
          placeholder="Paste any text containing claims to verify..."
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
        />
      ) : (
        <input
          className="w-full p-4 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-indigo-500 transition"
          placeholder="Paste an article URL to fact-check..."
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
        />
      )}

      <div className="text-center mt-4 flex justify-center gap-3">
        <button
          onClick={onSubmit}
          disabled={loading}
          className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-8 py-3 rounded-full font-semibold hover:shadow-lg disabled:opacity-50 transition"
        >
          {loading ? "Checking..." : "Check Facts"}
        </button>
        {loading && (
          <button
            onClick={onCancel}
            className="px-6 py-3 rounded-full font-semibold border border-white/30 text-gray-500 hover:bg-gray-100 transition"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
