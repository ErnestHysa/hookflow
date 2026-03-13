"use client"

import { Webhook, Calendar, Activity, ExternalLink } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatDate, truncate } from "@/lib/utils"

interface WebhookCardProps {
  webhook: {
    id: string
    status: string
    created_at: string
    body: Record<string, unknown>
    headers: Record<string, string>
  }
  onViewDetails: (id: string) => void
}

export function WebhookCard({ webhook, onViewDetails }: WebhookCardProps) {
  const getStatusVariant = (status: string) => {
    switch (status) {
      case "completed": return "success"
      case "failed": return "destructive"
      case "processing": return "warning"
      default: return "default"
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Webhook className="w-5 h-5 text-slate-400" />
            <CardTitle className="text-sm font-mono">
              {truncate(webhook.id, 20)}
            </CardTitle>
          </div>
          <Badge variant={getStatusVariant(webhook.status) as never}>
            {webhook.status}
          </Badge>
        </div>
        <CardDescription className="flex items-center gap-1 text-xs">
          <Calendar className="w-3 h-3" />
          {formatDate(webhook.created_at)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Payload Preview</p>
            <pre className="text-xs bg-slate-100 p-2 rounded overflow-hidden">
              {truncate(JSON.stringify(webhook.body, null, 2), 150)}
            </pre>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => onViewDetails(webhook.id)}
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            View Details
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
