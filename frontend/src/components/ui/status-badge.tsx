interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    success: "bg-green-100 text-green-800",
    retrying: "bg-orange-100 text-orange-800",
    active: "bg-green-100 text-green-800",
    inactive: "bg-gray-100 text-gray-800",
  };

  const defaultColor = "bg-gray-100 text-gray-800";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        colors[status] || defaultColor
      }`}
    >
      {status}
    </span>
  );
}
