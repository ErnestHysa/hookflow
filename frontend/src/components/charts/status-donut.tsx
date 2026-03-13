"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

interface StatusDonutProps {
  data: Record<string, number>;
}

const COLORS: Record<string, string> = {
  completed: "#22c55e",
  success: "#22c55e",
  pending: "#eab308",
  processing: "#3b82f6",
  failed: "#ef4444",
};

const STATUS_LABELS: Record<string, string> = {
  completed: "Completed",
  success: "Success",
  pending: "Pending",
  processing: "Processing",
  failed: "Failed",
};

export function StatusDonut({ data }: StatusDonutProps) {
  const chartData = Object.entries(data)
    .filter(([_, count]) => count > 0)
    .map(([status, count]) => ({
      name: STATUS_LABELS[status] || status,
      value: count,
      color: COLORS[status] || "#64748b",
    }));

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        No data
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "#1e293b",
            border: "none",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          formatter={(value) => <span className="text-gray-600">{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
