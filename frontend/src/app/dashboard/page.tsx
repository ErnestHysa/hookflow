"use client";

import { useEffect, useState } from "react";
import { Webhook, Activity, Target, TrendingUp } from "lucide-react";
import { api, type Analytics } from "@/lib/api-clients";
import { StatCard } from "@/components/dashboard/stat-card";
import { WebhookChart } from "@/components/charts/webhook-chart";
import { StatusDonut } from "@/components/charts/status-donut";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  // For now, just show the first app's analytics
  // In Phase 5, this will be the user's apps
  useEffect(() => {
    async function loadAnalytics() {
      try {
        const apps = await api.getApps();
        if (apps.length > 0) {
          const appId = (apps[0] as { id: string }).id;
          const data = await api.getAnalytics(appId, "7d");
          setAnalytics(data);
        }
      } catch (err) {
        console.error("Failed to load analytics:", err);
        setError("Failed to load analytics");
      } finally {
        setLoading(false);
      }
    }

    loadAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-600">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="min-h-screen bg-slate-50">
        <header className="bg-white border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
            <h1 className="text-xl font-semibold">Dashboard</h1>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center py-12 bg-white rounded-lg border">
            <p className="text-gray-500 mb-4">No apps found.</p>
            <button
              onClick={() => window.location.href = "/"}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Create Your First App
            </button>
          </div>
        </main>
      </div>
    );
  }

  const successRate = analytics.success_rate.toFixed(1);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold">Dashboard</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Webhook}
            label="Webhooks (7d)"
            value={analytics.total_webhooks.toLocaleString()}
          />
          <StatCard
            icon={Activity}
            label="Success Rate"
            value={`${successRate}%`}
            changePositive={analytics.success_rate >= 90}
          />
          <StatCard
            icon={Target}
            label="Avg Response Time"
            value={`${Math.round(analytics.avg_response_time_ms)}ms`}
          />
          <StatCard
            icon={TrendingUp}
            label="Active Destinations"
            value={analytics.top_destinations.length}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Webhooks Over Time</h2>
            <WebhookChart data={analytics.webhooks_over_time} />
          </div>
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Delivery Status</h2>
            <StatusDonut data={analytics.webhooks_by_status} />
          </div>
        </div>
      </main>
    </div>
  );
}
