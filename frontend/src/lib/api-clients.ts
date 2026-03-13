// frontend/src/lib/api-clients.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface Webhook {
  id: string;
  app_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  body?: Record<string, unknown>;
  headers?: Record<string, string>;
}

export interface Delivery {
  id: string;
  webhook_id: string;
  destination_id: string;
  attempt_number: number;
  status: string;
  response_status_code?: number;
  error_message?: string;
  response_time_ms?: number;
  created_at: string;
}

export interface FailedDelivery {
  id: string;
  webhook_id: string;
  destination_id: string;
  destination_name: string;
  destination_type: string;
  attempt_number: number;
  status: string;
  error_message?: string;
  response_status_code?: number;
  response_time_ms?: number;
  retry_after?: string;
  created_at: string;
  webhook?: {
    id: string;
    body?: Record<string, unknown>;
    headers?: Record<string, string>;
  };
}

export interface DLQResponse {
  items: FailedDelivery[];
  total: number;
  limit: number;
  offset: number;
}

export interface DLQStats {
  total_failed: number;
  by_status: Record<string, number>;
  top_errors: Array<{ error: string; count: number }>;
}

export interface Analytics {
  total_webhooks: number;
  success_rate: number;
  avg_response_time_ms: number;
  webhooks_by_status: Record<string, number>;
  webhooks_over_time: Array<{ timestamp: string; count: number }>;
  top_destinations: Array<{ name: string; count: number; success_rate: number }>;
}

export interface Destination {
  id: string;
  app_id: string;
  name: string;
  type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at?: string;
  expires_at?: string;
  created_at: string;
}

export interface App {
  id: string;
  name: string;
  description?: string;
  monthly_limit: number;
  current_month_count: number;
  is_active: boolean;
  created_at: string;
}

// API Client functions
async function apiRequest(path: string, options?: RequestInit) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "API request failed");
  }

  return response.json();
}

export const api = {
  // Apps
  getApps: () => apiRequest("/apps"),
  getApp: (id: string) => apiRequest(`/apps/${id}`),
  createApp: (data: { name: string; description?: string }) =>
    apiRequest("/apps", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Analytics
  getAnalytics: (appId: string, period: string = "24h") =>
    apiRequest(`/apps/${appId}/analytics?period=${period}`),

  // Webhooks
  getWebhooks: (appId: string, limit = 50, offset = 0) =>
    apiRequest(`/webhooks/${appId}?limit=${limit}&offset=${offset}`),
  getWebhook: (webhookId: string) =>
    apiRequest(`/webhooks/detail/${webhookId}`),
  replayWebhook: (webhookId: string, destinationIds?: string[]) =>
    apiRequest(`/webhooks/${webhookId}/replay`, {
      method: "POST",
      body: JSON.stringify({ destination_ids: destinationIds }),
    }),

  // Destinations
  getDestinations: (appId: string) =>
    apiRequest(`/apps/${appId}/destinations`),
  createDestination: (appId: string, data: unknown) =>
    apiRequest(`/apps/${appId}/destinations`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  testDestination: (appId: string, destinationId: string, payload?: unknown) =>
    apiRequest(`/apps/${appId}/destinations/${destinationId}/test`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteDestination: (appId: string, destinationId: string) =>
    apiRequest(`/apps/${appId}/destinations/${destinationId}`, {
      method: "DELETE",
    }),

  // API Keys
  getApiKeys: (appId: string) =>
    apiRequest(`/apps/${appId}/api-keys`),
  createApiKey: (appId: string, data: { name: string; scopes?: string[]; expires_at?: string }) =>
    apiRequest(`/apps/${appId}/api-keys`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  revokeApiKey: (appId: string, keyId: string) =>
    apiRequest(`/apps/${appId}/api-keys/${keyId}`, {
      method: "DELETE",
    }),

  // Dead Letter Queue (Failed Deliveries)
  getFailedDeliveries: (appId: string, limit = 100, offset = 0, status?: string) =>
    apiRequest(`/apps/${appId}/dlq?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ""}`),
  getDLQStats: (appId: string) =>
    apiRequest(`/apps/${appId}/dlq/stats`),
  replayFailedDelivery: (deliveryId: string) =>
    apiRequest(`/dlq/${deliveryId}/replay`, {
      method: "POST",
    }),
  deleteFailedDelivery: (deliveryId: string) =>
    apiRequest(`/dlq/${deliveryId}`, {
      method: "DELETE",
    }),
  bulkReplayFailedDeliveries: (appId: string, deliveryIds: string[]) =>
    apiRequest(`/apps/${appId}/dlq/bulk-replay`, {
      method: "POST",
      body: JSON.stringify(deliveryIds),
    }),
  bulkDeleteFailedDeliveries: (appId: string, deliveryIds: string[]) =>
    apiRequest(`/apps/${appId}/dlq/bulk-delete`, {
      method: "POST",
      body: JSON.stringify(deliveryIds),
    }),
};
