"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api-clients";
import { WebhookDetail } from "@/components/dashboard/webhook-detail";
import { StatusBadge } from "@/components/ui/status-badge";

export default function WebhookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [webhook, setWebhook] = useState<any>(null);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);

  const webhookId = params.webhookId as string;
  const appId = params.id as string;

  useEffect(() => {
    async function loadWebhook() {
      try {
        const data = await api.getWebhook(webhookId);
        setWebhook(data);
        setDeliveries(data.deliveries || []);
      } catch (error) {
        console.error("Failed to load webhook:", error);
      } finally {
        setLoading(false);
      }
    }

    loadWebhook();
  }, [webhookId]);

  const handleReplay = async (destinationIds?: string[]) => {
    try {
      setReplaying(true);
      await api.replayWebhook(webhookId, destinationIds);
      // Reload webhook after replay
      const data = await api.getWebhook(webhookId);
      setWebhook(data);
      setDeliveries(data.deliveries || []);
    } catch (error) {
      console.error("Failed to replay webhook:", error);
      alert("Failed to replay webhook");
    } finally {
      setReplaying(false);
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!webhook) {
    return <div className="p-8">Webhook not found</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <button
            onClick={() => router.push(`/dashboard/app/${appId}/webhooks`)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            ← Back to Webhooks
          </button>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">Status:</span>
            <StatusBadge status={webhook.status} />
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Webhook Details</h1>
          <p className="text-sm text-gray-500 mt-1">
            ID: {webhookId} • Received: {new Date(webhook.created_at).toLocaleString()}
          </p>
        </div>

        <WebhookDetail
          webhook={webhook}
          deliveries={deliveries}
          onReplay={handleReplay}
        />
      </main>
    </div>
  );
}
