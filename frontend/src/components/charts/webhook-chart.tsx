"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface WebhookChartProps {
  data: Array<{ timestamp: string; count: number }>;
}

export function WebhookChart({ data }: WebhookChartProps) {
  // Format timestamp for display
  const formattedData = data.map((d) => ({
    ...d,
    time: new Date(d.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={formattedData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 12 }}
          stroke="#64748b"
        />
        <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1e293b",
            border: "none",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
