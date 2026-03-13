"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api-clients";

interface ApiKeyFormProps {
  appId: string;
  onSuccess: (fullKey: string) => void;
  onCancel: () => void;
}

export function ApiKeyForm({ appId, onSuccess, onCancel }: ApiKeyFormProps) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read", "write"]);
  const [expiresIn, setExpiresIn] = useState<"never" | "30" | "90" | "365">("never");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const availableScopes = [
    { value: "read", label: "Read - View webhooks and apps" },
    { value: "write", label: "Write - Create and replay webhooks" },
    { value: "admin", label: "Admin - Full access including destinations" },
  ];

  const toggleScope = (scope: string) => {
    if (scopes.includes(scope)) {
      setScopes(scopes.filter((s) => s !== scope));
    } else {
      setScopes([...scopes, scope]);
    }
  };

  const calculateExpiresAt = () => {
    if (expiresIn === "never") return undefined;
    const date = new Date();
    date.setDate(date.getDate() + parseInt(expiresIn));
    return date.toISOString();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await api.createApiKey(appId, {
        name,
        scopes,
        expires_at: calculateExpiresAt(),
      });
      // The full key is only returned once
      onSuccess(result.key || result.id);
    } catch (err: any) {
      setError(err.message || "Failed to create API key");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Create API Key</h2>
          <button
            onClick={onCancel}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              placeholder="My API Key"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Scopes</label>
            <div className="space-y-2">
              {availableScopes.map((scope) => (
                <label key={scope.value} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={scopes.includes(scope.value)}
                    onChange={() => toggleScope(scope.value)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{scope.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Expires In</label>
            <select
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={expiresIn}
              onChange={(e) => setExpiresIn(e.target.value as any)}
            >
              <option value="never">Never</option>
              <option value="30">30 Days</option>
              <option value="90">90 Days</option>
              <option value="365">1 Year</option>
            </select>
          </div>

          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              <strong>Important:</strong> Copy your API key now. You won't be able to see it again.
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
