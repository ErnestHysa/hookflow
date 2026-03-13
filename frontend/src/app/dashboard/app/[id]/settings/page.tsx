"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { api, type ApiKey, type App } from "@/lib/api-clients";
import { ApiKeyList } from "@/components/dashboard/api-key-list";
import { ApiKeyForm } from "@/components/dashboard/api-key-form";

export default function SettingsPage() {
  const params = useParams();
  const router = useRouter();
  const [app, setApp] = useState<App | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);

  const appId = params.id as string;

  useEffect(() => {
    async function loadData() {
      try {
        const [appData, keysData] = await Promise.all([
          api.getApp(appId),
          api.getApiKeys(appId),
        ]);
        setApp(appData);
        setApiKeys(keysData);
      } catch (error) {
        console.error("Failed to load settings:", error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [appId]);

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm("Are you sure you want to revoke this API key? This action cannot be undone.")) return;

    try {
      await api.revokeApiKey(appId, keyId);
      setApiKeys(apiKeys.filter((k) => k.id !== keyId));
    } catch (error: any) {
      console.error("Failed to revoke key:", error);
      alert(`Failed to revoke key: ${error.message}`);
    }
  };

  const handleCopyKey = async (keyId: string) => {
    // Note: We can only copy the full key right after creation
    // For existing keys, we only show the prefix
    alert("Full API keys are only shown once at creation. Please create a new key if you've lost this one.");
  };

  const handleKeyCreated = (fullKey: string) => {
    setShowKeyForm(false);
    setNewKey(fullKey);
    // Reload keys
    api.getApiKeys(appId).then(setApiKeys);
  };

  const copyNewKeyToClipboard = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      alert("API key copied to clipboard!");
      setNewKey(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="p-8">Loading...</div>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="p-8">App not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <button
            onClick={() => router.push(`/dashboard/app/${appId}`)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            ← Back to App
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your app configuration and API keys
          </p>
        </div>

        {/* API Keys Section */}
        <div className="bg-white rounded-lg border p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">API Keys</h2>
            <button
              onClick={() => setShowKeyForm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              Create Key
            </button>
          </div>

          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              API keys are used to authenticate API requests. Keep them secure and never share them publicly.
            </p>
          </div>

          <ApiKeyList
            apiKeys={apiKeys}
            onDelete={handleRevokeKey}
            onCopy={handleCopyKey}
          />
        </div>

        {/* App Info Section */}
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4">App Information</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-gray-500">App ID</label>
              <p className="text-sm font-mono bg-gray-50 p-2 rounded mt-1">{app.id}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Name</label>
              <p className="text-sm mt-1">{app.name}</p>
            </div>
            {app.description && (
              <div>
                <label className="text-sm font-medium text-gray-500">Description</label>
                <p className="text-sm mt-1">{app.description}</p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-500">Monthly Limit</label>
                <p className="text-sm mt-1">{app.monthly_limit.toLocaleString()}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">Current Month</label>
                <p className="text-sm mt-1">{app.current_month_count.toLocaleString()}</p>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Status</label>
              <p className="text-sm mt-1">
                {app.is_active ? (
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded">Active</span>
                ) : (
                  <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">Inactive</span>
                )}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Created</label>
              <p className="text-sm mt-1">{new Date(app.created_at).toLocaleString()}</p>
            </div>
          </div>
        </div>
      </main>

      {showKeyForm && (
        <ApiKeyForm
          appId={appId}
          onSuccess={handleKeyCreated}
          onCancel={() => setShowKeyForm(false)}
        />
      )}

      {newKey && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 p-6">
            <h2 className="text-lg font-semibold mb-4">Your API Key</h2>
            <p className="text-sm text-gray-600 mb-4">
              Copy this key now. You won't be able to see it again.
            </p>
            <div className="bg-gray-100 p-3 rounded-lg font-mono text-sm break-all mb-4">
              {newKey}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setNewKey(null)}
                className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Close
              </button>
              <button
                onClick={copyNewKeyToClipboard}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Copy to Clipboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
