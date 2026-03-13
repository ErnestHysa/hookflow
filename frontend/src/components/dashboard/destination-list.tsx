"use client";

import { useState } from "react";
import { Trash2, TestTube } from "lucide-react";
import { type Destination } from "@/lib/api-clients";
import { StatusBadge } from "@/components/ui/status-badge";

interface DestinationListProps {
  destinations: Destination[];
  onDelete: (id: string) => void;
  onTest: (id: string) => void;
}

export function DestinationList({ destinations, onDelete, onTest }: DestinationListProps) {
  if (destinations.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No destinations configured. Add one to start receiving webhooks.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {destinations.map((dest) => (
        <div key={dest.id} className="flex items-center justify-between p-4 border rounded-lg">
          <div>
            <h3 className="font-medium">{dest.name}</h3>
            <p className="text-sm text-gray-500 capitalize">{dest.type}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={dest.is_active ? "active" : "inactive"} />
            <button
              onClick={() => onTest(dest.id)}
              className="p-2 hover:bg-gray-100 rounded"
              title="Test destination"
            >
              <TestTube className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(dest.id)}
              className="p-2 hover:bg-red-50 text-red-600 rounded"
              title="Delete destination"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
