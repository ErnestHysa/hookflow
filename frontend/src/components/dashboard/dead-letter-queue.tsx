"use client"

import { useState, useEffect } from "react"
import { api, type FailedDelivery, type DLQStats } from "@/lib/api-clients"
import { StatusBadge } from "@/components/ui/status-badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { JsonViewer } from "@/components/ui/json-viewer"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  RotateCcw,
  Trash2,
  AlertTriangle,
  XCircle,
  Clock,
} from "lucide-react"

interface DeadLetterQueueProps {
  appId: string
}

export function DeadLetterQueue({ appId }: DeadLetterQueueProps) {
  const [deliveries, setDeliveries] = useState<FailedDelivery[]>([])
  const [stats, setStats] = useState<DLQStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [selectedDelivery, setSelectedDelivery] = useState<FailedDelivery | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const limit = 50

  const fetchFailedDeliveries = async () => {
    try {
      setLoading(true)
      const data = await api.getFailedDeliveries(appId, limit, page * limit)
      setDeliveries(data.items)
      setTotal(data.total)
    } catch (error) {
      console.error("Failed to fetch DLQ:", error)
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const data = await api.getDLQStats(appId)
      setStats(data)
    } catch (error) {
      console.error("Failed to fetch DLQ stats:", error)
    }
  }

  useEffect(() => {
    fetchFailedDeliveries()
    fetchStats()
  }, [appId, page])

  const handleReplay = async (deliveryId: string) => {
    try {
      setActionLoading(deliveryId)
      await api.replayFailedDelivery(deliveryId)
      // Refresh the list
      await fetchFailedDeliveries()
      await fetchStats()
    } catch (error) {
      console.error("Failed to replay:", error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (deliveryId: string) => {
    if (!confirm("Are you sure you want to delete this failed delivery?")) {
      return
    }
    try {
      setActionLoading(deliveryId)
      await api.deleteFailedDelivery(deliveryId)
      // Refresh the list
      await fetchFailedDeliveries()
      await fetchStats()
    } catch (error) {
      console.error("Failed to delete:", error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleBulkReplay = async () => {
    if (selectedIds.size === 0) return
    try {
      setActionLoading("bulk")
      await api.bulkReplayFailedDeliveries(appId, Array.from(selectedIds))
      setSelectedIds(new Set())
      await fetchFailedDeliveries()
      await fetchStats()
    } catch (error) {
      console.error("Failed to bulk replay:", error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Are you sure you want to delete ${selectedIds.size} failed deliveries?`)) {
      return
    }
    try {
      setActionLoading("bulk")
      await api.bulkDeleteFailedDeliveries(appId, Array.from(selectedIds))
      setSelectedIds(new Set())
      await fetchFailedDeliveries()
      await fetchStats()
    } catch (error) {
      console.error("Failed to bulk delete:", error)
    } finally {
      setActionLoading(null)
    }
  }

  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedIds(newSet)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "retrying":
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <AlertTriangle className="h-4 w-4" />
    }
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-6">
      {/* Stats Header */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Failed</p>
                <p className="text-2xl font-semibold">{stats.total_failed}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Retrying</p>
                <p className="text-2xl font-semibold">{stats.by_status.retrying || 0}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <AlertTriangle className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Permanently Failed</p>
                <p className="text-2xl font-semibold">{stats.by_status.failed || 0}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              fetchFailedDeliveries()
              fetchStats()
            }}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          {selectedIds.size > 0 && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBulkReplay}
                disabled={actionLoading === "bulk"}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                Replay ({selectedIds.size})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBulkDelete}
                disabled={actionLoading === "bulk"}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete ({selectedIds.size})
              </Button>
            </>
          )}
        </div>

        <div className="text-sm text-gray-500">
          {total} failed {total === 1 ? "delivery" : "deliveries"}
        </div>
      </div>

      {/* Failed Deliveries List */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading failed deliveries...</div>
        ) : deliveries.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No failed deliveries</p>
            <p className="text-sm mt-1">Webhooks that fail to deliver will appear here</p>
          </div>
        ) : (
          <div className="divide-y">
            {deliveries.map((delivery) => (
              <div
                key={delivery.id}
                className="p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start gap-4">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(delivery.id)}
                    onChange={() => toggleSelection(delivery.id)}
                    className="mt-1"
                  />

                  <div className="flex-shrink-0">
                    {getStatusIcon(delivery.status)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{delivery.destination_name}</p>
                          <StatusBadge status={delivery.status} />
                        </div>
                        <p className="text-sm text-gray-500">
                          {delivery.destination_type} • Attempt #{delivery.attempt_number}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedDelivery(delivery)}
                        >
                          View Details
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReplay(delivery.id)}
                          disabled={actionLoading === delivery.id}
                        >
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(delivery.id)}
                          disabled={actionLoading === delivery.id}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {delivery.error_message && (
                      <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-700 font-mono overflow-x-auto">
                        {delivery.error_message}
                      </div>
                    )}

                    <div className="mt-2 text-xs text-gray-400">
                      {new Date(delivery.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <span className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}

      {/* Delivery Detail Dialog */}
      <Dialog
        open={!!selectedDelivery}
        onOpenChange={(open) => !open && setSelectedDelivery(null)}
      >
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Failed Delivery Details</DialogTitle>
          </DialogHeader>

          {selectedDelivery && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <p className="font-medium flex items-center gap-2">
                    {getStatusIcon(selectedDelivery.status)}
                    {selectedDelivery.status}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Attempt</p>
                  <p className="font-medium">#{selectedDelivery.attempt_number}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Destination</p>
                  <p className="font-medium">{selectedDelivery.destination_name}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Type</p>
                  <p className="font-medium">{selectedDelivery.destination_type}</p>
                </div>
                {selectedDelivery.response_status_code && (
                  <div>
                    <p className="text-sm text-gray-500">Status Code</p>
                    <p className="font-medium">{selectedDelivery.response_status_code}</p>
                  </div>
                )}
                {selectedDelivery.response_time_ms && (
                  <div>
                    <p className="text-sm text-gray-500">Response Time</p>
                    <p className="font-medium">{selectedDelivery.response_time_ms}ms</p>
                  </div>
                )}
              </div>

              {selectedDelivery.error_message && (
                <div>
                  <p className="text-sm text-gray-500 mb-2">Error Message</p>
                  <div className="p-3 bg-red-50 rounded-lg text-sm text-red-700">
                    {selectedDelivery.error_message}
                  </div>
                </div>
              )}

              {selectedDelivery.webhook?.body && (
                <div>
                  <p className="text-sm text-gray-500 mb-2">Webhook Payload</p>
                  <JsonViewer data={selectedDelivery.webhook.body} />
                </div>
              )}

              {selectedDelivery.webhook?.headers && (
                <div>
                  <p className="text-sm text-gray-500 mb-2">Headers</p>
                  <JsonViewer data={selectedDelivery.webhook.headers} />
                </div>
              )}

              <div className="flex justify-end gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    if (selectedDelivery) {
                      handleReplay(selectedDelivery.id)
                      setSelectedDelivery(null)
                    }
                  }}
                  disabled={actionLoading === selectedDelivery.id}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Replay
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (selectedDelivery) {
                      handleDelete(selectedDelivery.id)
                      setSelectedDelivery(null)
                    }
                  }}
                  disabled={actionLoading === selectedDelivery.id}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
