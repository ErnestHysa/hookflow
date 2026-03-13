"use client"

import { useState } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface DestinationFormProps {
  appId: string
  onClose: () => void
  onSubmit: (data: DestinationFormData) => void
}

export interface DestinationFormData {
  name: string
  type: string
  config: Record<string, string>
}

const destinationTypes = [
  { value: "http", label: "HTTP Webhook", description: "Send to any HTTP endpoint" },
  { value: "slack", label: "Slack", description: "Send to Slack webhook" },
  { value: "discord", label: "Discord", description: "Send to Discord webhook" },
  { value: "database", label: "Database", description: "Store in PostgreSQL database" },
]

export function DestinationForm({ appId, onClose, onSubmit }: DestinationFormProps) {
  const [name, setName] = useState("")
  const [type, setType] = useState("http")
  const [config, setConfig] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      await onSubmit({ name, type, config })
      onClose()
    } finally {
      setLoading(false)
    }
  }

  const renderConfigFields = () => {
    switch (type) {
      case "http":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="url">Endpoint URL</Label>
              <Input
                id="url"
                type="url"
                placeholder="https://api.example.com/webhook"
                value={config.url || ""}
                onChange={(e) => setConfig({ ...config, url: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="headers">Custom Headers (JSON)</Label>
              <Input
                id="headers"
                placeholder='{"Authorization": "Bearer token"}'
                value={config.headers || ""}
                onChange={(e) => setConfig({ ...config, headers: e.target.value })}
              />
            </div>
          </div>
        )
      case "slack":
      case "discord":
        return (
          <div>
            <Label htmlFor="webhook_url">Webhook URL</Label>
            <Input
              id="webhook_url"
              type="url"
              placeholder="https://hooks.slack.com/services/..."
              value={config.webhook_url || ""}
              onChange={(e) => setConfig({ ...config, webhook_url: e.target.value })}
              required
            />
          </div>
        )
      case "database":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="host">Database Host</Label>
              <Input
                id="host"
                placeholder="localhost:5432"
                value={config.host || ""}
                onChange={(e) => setConfig({ ...config, host: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="dbname">Database Name</Label>
              <Input
                id="dbname"
                placeholder="webhooks"
                value={config.dbname || ""}
                onChange={(e) => setConfig({ ...config, dbname: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="table">Table Name</Label>
              <Input
                id="table"
                placeholder="events"
                value={config.table || ""}
                onChange={(e) => setConfig({ ...config, table: e.target.value })}
              />
            </div>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold">Add Destination</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="Production API"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {destinationTypes.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    <div>
                      <div className="font-medium">{t.label}</div>
                      <div className="text-xs text-slate-500">{t.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {renderConfigFields()}

          <div className="flex gap-3 pt-4">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={loading}>
              {loading ? "Creating..." : "Create Destination"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
