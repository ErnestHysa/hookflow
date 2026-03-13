"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { api, type Destination } from "@/lib/api-clients";
import { DestinationList } from "@/components/dashboard/destination-list";
import { DestinationForm } from "@/components/dashboard/destination-form";

export default function DestinationsPage() {
  const params = useParams();
  const router = useRouter();
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const appId = params.id as string;

  useEffect(() => {
    loadDestinations().finally(() => setLoading(false));
  }, [appId]);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this destination?")) return;

    try {
      await api.deleteDestination(appId, id);
      setDestinations(destinations.filter((d) => d.id !== id));
    } catch (error) {
      console.error("Failed to delete destination:", error);
      alert("Failed to delete destination");
    }
  };

  const handleTest = async (id: string) => {
    try {
      await api.testDestination(appId, id);
      alert("Test webhook sent successfully!");
    } catch (error: any) {
      console.error("Failed to test destination:", error);
      alert(`Failed to test destination: ${error.message}`);
    }
  };

  const loadDestinations = async () => {
    try {
      const data = await api.getDestinations(appId);
      setDestinations(data);
    } catch (error) {
      console.error("Failed to load destinations:", error);
    }
  };

  const handleSubmit = async (data: { name: string; type: string; config: Record<string, string> }) => {
    try {
      await api.createDestination(appId, data);
      await loadDestinations();
      setShowForm(false);
    } catch (error: any) {
      console.error("Failed to create destination:", error);
      alert(`Failed to create destination: ${error.message}`);
      throw error;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <button
            onClick={() => router.push(`/dashboard/app/${appId}`)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            ← Back to App
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Add Destination
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Destinations</h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure where webhooks are delivered
          </p>
        </div>

        <div className="bg-white rounded-lg border p-6">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : (
            <DestinationList
              destinations={destinations}
              onDelete={handleDelete}
              onTest={handleTest}
            />
          )}
        </div>
      </main>

      {showForm && (
        <DestinationForm
          appId={appId}
          onClose={() => setShowForm(false)}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
