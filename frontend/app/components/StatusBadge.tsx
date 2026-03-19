import { STATUS_BADGE_STYLES } from "../lib/constants";

type StatusBadgeProps = {
  status: string;
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`ml-3 px-3 py-1 rounded-full text-sm font-semibold whitespace-nowrap ${
        STATUS_BADGE_STYLES[status] || "bg-gray-100 text-gray-700"
      }`}
    >
      {status}
    </span>
  );
}
