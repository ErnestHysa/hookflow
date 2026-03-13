"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Copy, Plus, Settings } from "lucide-react";
import { api, type App, type Analytics, type Webhook } from "@/lib/api-clients";
import { StatCard } from "@/components/dashboard/stat-card";
import { WebhookTable } from "@/components/dashboard/webhook-table";
import { Webhook as WebhookIcon, Activity } from "lucide-react";

export default function AppDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [app, setApp] = useState<App | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);

  const appId = params.id as string;

  useEffect(() => {
    async function loadData() {
      try {
        const [appData, analyticsData, webhooksData] = await Promise.all([
          api.getApp(appId),
          api.getAnalytics(appId, "24h"),
          api.getWebhooks(appId, 10),
        ]);
        setApp(appData);
        setAnalytics(analyticsData);
        setWebhooks(webhooksData);
      } catch (error) {
        console.error("Failed to load app data:", error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [appId]);

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!app) {
    return <div className="p-8">App not found</div>;
  }

  const webhookUrl = `${window.location.origin}/api/v1/webhook/${appId}`;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <h1 className="text-xl font-semibold">{app.name}</h1>
          <div className="flex gap-2">
            <button
              onClick={() => router.push(`/dashboard/app/${appId}/destinations`)}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Add Destination
            </button>
            <button
              onClick={() => router.push(`/dashboard/app/${appId}/settings`)}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 flex items-center gap-1"
            >
              <Settings className="w-4 h-4" />
              Settings
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* App Info */}
        <div className="bg-white rounded-lg border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Webhook URL</h2>
          <div className="flex items-center gap-2 p-3 bg-slate-100 rounded-lg">
            <code className="flex-1 text-sm font-mono">{webhookUrl}</code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(webhookUrl);
                alert("Copied to clipboard!");
              }}
              className="p-2 hover:bg-slate-200 rounded"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Stats */}
        {analytics && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <StatCard icon={WebhookIcon} label="Total Webhooks" value={analytics.total_webhooks} />
            <StatCard icon={Activity} label="Success Rate" value={`${analytics.success_rate.toFixed(1)}%`} />
            <StatCard icon={Activity} label="Avg Response" value={`${Math.round(analytics.avg_response_time_ms)}ms`} />
          </div>
        )}

        {/* Recent Webhooks */}
        <div className="bg-white rounded-lg border">
          <div className="px-6 py-4 border-b flex justify-between items-center">
            <h2 className="text-lg font-semibold">Recent Webhooks</h2>
            <button
              onClick={() => router.push(`/dashboard/app/${appId}/webhooks`)}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              View All
            </button>
          </div>
          <WebhookTable webhooks={webhooks} />
        </div>
      </main>
    </div>
  );
}
