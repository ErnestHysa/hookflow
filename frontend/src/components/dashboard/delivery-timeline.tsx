import { CheckCircle, XCircle, Clock } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

interface Delivery {
  id: string;
  destination_id: string;
  attempt_number: number;
  status: string;
  response_status_code?: number;
  error_message?: string;
  response_time_ms?: number;
  created_at: string;
}

interface DeliveryTimelineProps {
  deliveries: Delivery[];
}

export function DeliveryTimeline({ deliveries }: DeliveryTimelineProps) {
  if (deliveries.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No delivery attempts yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {deliveries.map((delivery, index) => {
        const isSuccess = delivery.status === "success";
        const isFailed = delivery.status === "failed";
        const isPending = delivery.status === "pending" || delivery.status === "retrying";

        return (
          <div key={delivery.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                isSuccess ? "bg-green-100" : isFailed ? "bg-red-100" : "bg-gray-100"
              }`}>
                {isSuccess && <CheckCircle className="w-4 h-4 text-green-600" />}
                {isFailed && <XCircle className="w-4 h-4 text-red-600" />}
                {isPending && <Clock className="w-4 h-4 text-gray-400" />}
              </div>
              {index < deliveries.length - 1 && (
                <div className="w-0.5 flex-1 bg-gray-200 my-1" />
              )}
            </div>

            <div className="flex-1 pb-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium">Attempt {delivery.attempt_number}</span>
                <StatusBadge status={delivery.status} />
              </div>

              {delivery.response_status_code && (
                <p className="text-sm text-gray-600">
                  Status: {delivery.response_status_code}
                </p>
              )}

              {delivery.response_time_ms && (
                <p className="text-sm text-gray-600">
                  Response time: {delivery.response_time_ms}ms
                </p>
              )}

              {delivery.error_message && (
                <p className="text-sm text-red-600 mt-1">
                  Error: {delivery.error_message}
                </p>
              )}

              <p className="text-xs text-gray-400 mt-1">
                {new Date(delivery.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
