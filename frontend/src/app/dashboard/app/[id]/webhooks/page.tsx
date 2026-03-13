"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Webhook } from "@/lib/api-clients";
import { WebhookTable } from "@/components/dashboard/webhook-table";

export default function WebhooksPage() {
  const params = useParams();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);

  const appId = params.id as string;
  const limit = 50;

  useEffect(() => {
    async function loadWebhooks() {
      try {
        setLoading(true);
        const data = await api.getWebhooks(appId, limit, page * limit);
        setWebhooks(data);
      } catch (error) {
        console.error("Failed to load webhooks:", error);
      } finally {
        setLoading(false);
      }
    }

    loadWebhooks();
  }, [appId, page]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold">Webhooks</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg border">
          <WebhookTable webhooks={webhooks} loading={loading} />

          {/* Pagination */}
          <div className="px-6 py-4 border-t flex justify-between items-center">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-4 py-2 text-sm border rounded-lg disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={webhooks.length < limit}
              className="px-4 py-2 text-sm border rounded-lg disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
