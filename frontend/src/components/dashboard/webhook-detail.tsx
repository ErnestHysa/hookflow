import { type Webhook, type Delivery } from "@/lib/api-clients";
import { JsonViewer } from "@/components/ui/json-viewer";
import { DeliveryTimeline } from "@/components/dashboard/delivery-timeline";

interface WebhookDetailProps {
  webhook: Webhook;
  deliveries: Delivery[];
  onReplay: (destinationIds?: string[]) => void;
}

export function WebhookDetail({ webhook, deliveries, onReplay }: WebhookDetailProps) {
  return (
    <div className="space-y-6">
      {/* Headers */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Request Headers</h3>
        <JsonViewer data={webhook.headers || {}} />
      </div>

      {/* Body */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Request Body</h3>
        <JsonViewer data={webhook.body || {}} />
      </div>

      {/* Deliveries */}
      <div className="bg-white rounded-lg border p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Delivery Attempts</h3>
          <button
            onClick={() => onReplay()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Replay Webhook
          </button>
        </div>
        <DeliveryTimeline deliveries={deliveries} />
      </div>
    </div>
  );
}
