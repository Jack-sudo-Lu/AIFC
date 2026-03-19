type ConfidenceBarProps = {
  score: number;
};

export default function ConfidenceBar({ score }: ConfidenceBarProps) {
  const color =
    score >= 0.7
      ? "bg-gradient-to-r from-indigo-500 to-purple-600"
      : score >= 0.4
      ? "bg-yellow-400"
      : "bg-red-400";

  return (
    <div className="mb-3">
      <div className="text-sm text-gray-500 mb-1">
        Confidence: {Math.round(score * 100)}%
      </div>
      <div className="h-2 bg-gray-200 rounded-full">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
    </div>
  );
}
