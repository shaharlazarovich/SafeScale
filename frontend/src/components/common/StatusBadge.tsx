import clsx from "clsx";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const colorMap: Record<string, string> = {
  connected: "bg-emerald-100 text-emerald-800",
  completed: "bg-emerald-100 text-emerald-800",
  high: "bg-emerald-100 text-emerald-800",
  success: "bg-emerald-100 text-emerald-800",
  eligible: "bg-emerald-100 text-emerald-800",

  running: "bg-amber-100 text-amber-800",
  medium: "bg-amber-100 text-amber-800",
  pending: "bg-amber-100 text-amber-800",
  partial: "bg-amber-100 text-amber-800",
  paused: "bg-amber-100 text-amber-800",

  error: "bg-red-100 text-red-800",
  failed: "bg-red-100 text-red-800",
  low: "bg-red-100 text-red-800",
  cancelled: "bg-red-100 text-red-800",

  in_progress: "bg-blue-100 text-blue-800",
  ineligible_builtin: "bg-gray-100 text-gray-600",
  ineligible_tier1: "bg-gray-100 text-gray-600",
  unknown: "bg-gray-100 text-gray-600",
  unclassified: "bg-gray-100 text-gray-600",
};

export default function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
  const colors = colorMap[status] ?? "bg-gray-100 text-gray-700";

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full font-medium capitalize",
        colors,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
