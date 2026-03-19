// Badge styles for claim status
export const STATUS_BADGE_STYLES: Record<string, string> = {
  SUPPORTED: "bg-green-100 text-green-800 border border-green-300",
  REFUTED: "bg-red-100 text-red-800 border border-red-300",
  NEI: "bg-yellow-100 text-yellow-800 border border-yellow-300",
};

// Match styles for decomposition
export const MATCH_STYLES: Record<string, string> = {
  confirmed: "text-green-600",
  contradicted: "text-red-600",
  missing: "text-gray-400",
};

// Credibility tiers
export type CredibilityBadge = { label: string; style: string };

export function getCredibilityBadge(score: number): CredibilityBadge {
  if (score >= 0.9) return { label: "Official", style: "bg-blue-100 text-blue-700" };
  if (score >= 0.7) return { label: "Trusted", style: "bg-green-100 text-green-700" };
  if (score >= 0.5) return { label: "Mainstream", style: "bg-gray-100 text-gray-700" };
  if (score >= 0.3) return { label: "General", style: "bg-yellow-100 text-yellow-700" };
  return { label: "Low", style: "bg-red-100 text-red-700" };
}

// API URL
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
