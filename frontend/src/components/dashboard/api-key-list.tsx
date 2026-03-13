import { type ApiKey } from "@/lib/api-clients";
import { Trash2, Copy, Key } from "lucide-react";

interface ApiKeyListProps {
  apiKeys: ApiKey[];
  onDelete: (id: string) => void;
  onCopy: (key: string) => void;
}

export function ApiKeyList({ apiKeys, onDelete, onCopy }: ApiKeyListProps) {
  if (apiKeys.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No API keys configured. Create one to authenticate your API requests.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {apiKeys.map((key) => (
        <div key={key.id} className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 rounded-lg">
              <Key className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <h3 className="font-medium">{key.name}</h3>
              <p className="text-sm text-gray-500 font-mono">{key.key_prefix}••••••••</p>
              <div className="flex gap-2 mt-1">
                <span className="text-xs text-gray-400">
                  Created: {new Date(key.created_at).toLocaleDateString()}
                </span>
                {key.last_used_at && (
                  <span className="text-xs text-gray-400">
                    Last used: {new Date(key.last_used_at).toLocaleDateString()}
                  </span>
                )}
                {key.expires_at && (
                  <span className="text-xs text-gray-400">
                    Expires: {new Date(key.expires_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {key.scopes.length > 0 && (
              <div className="flex gap-1 mr-2">
                {key.scopes.map((scope) => (
                  <span
                    key={scope}
                    className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded"
                  >
                    {scope}
                  </span>
                ))}
              </div>
            )}
            <button
              onClick={() => onCopy(key.id)}
              className="p-2 hover:bg-gray-100 rounded"
              title="Copy key"
            >
              <Copy className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(key.id)}
              className="p-2 hover:bg-red-50 text-red-600 rounded"
              title="Revoke key"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
