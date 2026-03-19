type ResultsSummaryProps = {
  total: number;
  supported: number;
  refuted: number;
  nei: number;
};

export default function ResultsSummary({ total, supported, refuted, nei }: ResultsSummaryProps) {
  return (
    <div className="text-white text-sm opacity-80 px-2">
      Found {total} claim{total !== 1 ? "s" : ""} &mdash;{" "}
      {supported} supported, {refuted} refuted, {nei} insufficient evidence
    </div>
  );
}
