"use client"

import { Link, Plus, Activity, TrendingUp } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { formatDate } from "@/lib/utils"

interface AppCardProps {
  app: {
    id: string
    name: string
    description: string | null
    monthly_limit: number
    current_month_count: number
    webhook_url: string
    created_at: string
  }
  onManage: (id: string) => void
  onCreateDestination: (id: string) => void
}

export function AppCard({ app, onManage, onCreateDestination }: AppCardProps) {
  const usagePercent = (app.current_month_count / app.monthly_limit) * 100

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>{app.name}</CardTitle>
            <CardDescription>{app.description || "No description"}</CardDescription>
          </div>
          <Link className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center">
            <Link className="w-4 h-4 text-slate-500" />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-slate-500">Monthly Usage</span>
            <span className="font-medium">
              {app.current_month_count.toLocaleString()} / {app.monthly_limit.toLocaleString()}
            </span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-slate-900 rounded-full transition-all"
              style={{ width: `${Math.min(usagePercent, 100)}%` }}
            />
          </div>
        </div>

        <div className="bg-slate-50 p-3 rounded-lg">
          <p className="text-xs font-medium text-slate-500 mb-1">Webhook URL</p>
          <p className="text-xs font-mono truncate">{app.webhook_url}</p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => onManage(app.id)}
          >
            <Activity className="w-4 h-4 mr-2" />
            View Webhooks
          </Button>
          <Button
            size="sm"
            className="w-full"
            onClick={() => onCreateDestination(app.id)}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Destination
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
