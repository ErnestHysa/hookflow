import { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  change?: string;
  changePositive?: boolean;
}

export function StatCard({
  icon: Icon,
  label,
  value,
  change,
  changePositive,
}: StatCardProps) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-slate-100 rounded-lg">
          <Icon className="w-5 h-5 text-slate-700" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-2xl font-semibold text-slate-900">{value}</p>
        </div>
        {change && (
          <span
            className={`text-sm ${
              changePositive ? "text-green-600" : "text-red-600"
            }`}
          >
            {change}
          </span>
        )}
      </div>
    </div>
  );
}
