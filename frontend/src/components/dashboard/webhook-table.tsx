import { StatusBadge } from "@/components/ui/status-badge";
import { type Webhook } from "@/lib/api-clients";
import { useRouter } from "next/navigation";

interface WebhookTableProps {
  webhooks: Webhook[];
  loading?: boolean;
}

export function WebhookTable({ webhooks, loading }: WebhookTableProps) {
  const router = useRouter();

  if (loading) {
    return <div className="p-4">Loading webhooks...</div>;
  }

  if (webhooks.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No webhooks received yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Timestamp</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Source</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Summary</th>
          </tr>
        </thead>
        <tbody>
          {webhooks.map((webhook) => (
            <tr
              key={webhook.id}
              onClick={() => router.push(`/dashboard/app/${webhook.app_id}/webhooks/${webhook.id}`)}
              className="border-b hover:bg-gray-50 cursor-pointer"
            >
              <td className="px-4 py-3 text-sm">
                {new Date(webhook.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-sm">
                <StatusBadge status={webhook.status} />
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {webhook.headers?.["x-forwarded-for"] || webhook.headers?.["user-agent"]?.substring(0, 30) || "-"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {webhook.body ? JSON.stringify(webhook.body).substring(0, 50) + "..." : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
