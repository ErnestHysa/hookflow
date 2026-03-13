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
  { value: "telegram", label: "Telegram", description: "Send to Telegram bot" },
  { value: "database", label: "Database", description: "Store in database table" },
  { value: "email", label: "Email", description: "Send via email" },
  { value: "notion", label: "Notion", description: "Create Notion database page" },
  { value: "airtable", label: "Airtable", description: "Create Airtable record" },
  { value: "google_sheets", label: "Google Sheets", description: "Append to spreadsheet" },
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
      case "telegram":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="bot_token">Bot Token</Label>
              <Input
                id="bot_token"
                type="text"
                placeholder="123456:ABC-DEF1234..."
                value={config.bot_token || ""}
                onChange={(e) => setConfig({ ...config, bot_token: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="chat_id">Chat ID</Label>
              <Input
                id="chat_id"
                type="text"
                placeholder="@channel or 123456789"
                value={config.chat_id || ""}
                onChange={(e) => setConfig({ ...config, chat_id: e.target.value })}
                required
              />
            </div>
          </div>
        )
      case "database":
        return (
          <div>
            <Label htmlFor="table_name">Table Name</Label>
            <Input
              id="table_name"
              type="text"
              placeholder="webhooks (default: webhooks_{app_id})"
              value={config.table_name || ""}
              onChange={(e) => setConfig({ ...config, table_name: e.target.value })}
            />
          </div>
        )
      case "email":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="provider">Provider</Label>
              <Select value={config.provider || "smtp"} onValueChange={(v) => setConfig({ ...config, provider: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="smtp">SMTP</SelectItem>
                  <SelectItem value="sendgrid">SendGrid</SelectItem>
                  <SelectItem value="ses">AWS SES</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="to">To Email</Label>
              <Input
                id="to"
                type="email"
                placeholder="recipient@example.com"
                value={config.to || ""}
                onChange={(e) => setConfig({ ...config, to: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="subject">Subject</Label>
              <Input
                id="subject"
                type="text"
                placeholder="New webhook notification"
                value={config.subject || ""}
                onChange={(e) => setConfig({ ...config, subject: e.target.value })}
              />
            </div>
          </div>
        )
      case "notion":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="api_key">API Key</Label>
              <Input
                id="api_key"
                type="password"
                placeholder="secret_..."
                value={config.api_key || ""}
                onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="database_id">Database ID</Label>
              <Input
                id="database_id"
                type="text"
                placeholder="32-character ID from Notion URL"
                value={config.database_id || ""}
                onChange={(e) => setConfig({ ...config, database_id: e.target.value })}
                required
              />
            </div>
          </div>
        )
      case "airtable":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="access_token">Access Token</Label>
              <Input
                id="access_token"
                type="password"
                placeholder="pat..."
                value={config.access_token || ""}
                onChange={(e) => setConfig({ ...config, access_token: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="base_id">Base ID</Label>
              <Input
                id="base_id"
                type="text"
                placeholder="app..."
                value={config.base_id || ""}
                onChange={(e) => setConfig({ ...config, base_id: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="table_id">Table ID</Label>
              <Input
                id="table_id"
                type="text"
                placeholder="tbl..."
                value={config.table_id || ""}
                onChange={(e) => setConfig({ ...config, table_id: e.target.value })}
                required
              />
            </div>
          </div>
        )
      case "google_sheets":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="spreadsheet_id">Spreadsheet ID</Label>
              <Input
                id="spreadsheet_id"
                type="text"
                placeholder="1Bxi... (from URL)"
                value={config.spreadsheet_id || ""}
                onChange={(e) => setConfig({ ...config, spreadsheet_id: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="sheet_name">Sheet Name (optional)</Label>
              <Input
                id="sheet_name"
                type="text"
                placeholder="Sheet1"
                value={config.sheet_name || ""}
                onChange={(e) => setConfig({ ...config, sheet_name: e.target.value })}
              />
            </div>
            <p className="text-xs text-gray-500">
              Uses Google service account configured server-side
            </p>
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
