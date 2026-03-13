"use client"

import { useState } from "react"
import { Copy, Plus, Webhook, Zap, Shield, Activity, Check, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { CodeBlock } from "@/components/ui/code-block"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

type CreateStep = "form" | "success"

export default function HomePage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [step, setStep] = useState<CreateStep>("form")
  const [appName, setAppName] = useState("")
  const [appDescription, setAppDescription] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [createdApp, setCreatedApp] = useState<{ id: string; name: string; webhook_secret: string; webhook_url: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const handleCreateApp = async () => {
    if (!appName.trim()) {
      setError("App name is required")
      return
    }

    setLoading(true)
    setError("")

    try {
      const res = await fetch(`${API_BASE}/apps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: appName.trim(),
          description: appDescription.trim() || undefined,
        }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || "Failed to create app")
      }

      const data = await res.json()
      setCreatedApp({
        id: data.id,
        name: data.name,
        webhook_secret: data.webhook_secret,
        webhook_url: `${window.location.origin}/api/webhook/${data.id}`,
      })
      setStep("success")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create app")
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setDialogOpen(false)
    setStep("form")
    setAppName("")
    setAppDescription("")
    setError("")
    setCreatedApp(null)
    setCopied(false)
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Webhook className="w-8 h-8 text-slate-900" />
            <span className="text-xl font-bold">HookFlow</span>
          </div>
          <nav className="flex items-center gap-6">
            <a href="#features" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">Features</a>
            <a href="#docs" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">Docs</a>
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create App
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <main>
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-5xl font-bold tracking-tight mb-6">
              Reliable Webhook Infrastructure
              <span className="block text-slate-400">for Everyone</span>
            </h1>
            <p className="text-xl text-slate-600 mb-8">
              Stop building webhook infrastructure from scratch. Receive, store, transform,
              and deliver webhooks with guaranteed delivery and built-in retry logic.
            </p>
            <div className="flex gap-4 justify-center">
              <Button size="lg" onClick={() => setDialogOpen(true)}>
                <Plus className="w-5 h-5 mr-2" />
                Get Started Free
              </Button>
              <Button size="lg" variant="outline" asChild>
                <a href="#docs">Read the Docs</a>
              </Button>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <h2 className="text-3xl font-bold text-center mb-12">Why HookFlow?</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader>
                <Zap className="w-10 h-10 text-slate-900 mb-4" />
                <CardTitle>Instant Setup</CardTitle>
                <CardDescription>
                  Get a webhook URL in seconds. No servers to manage, no infrastructure to maintain.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Shield className="w-10 h-10 text-slate-900 mb-4" />
                <CardTitle>Guaranteed Delivery</CardTitle>
                <CardDescription>
                  Automatic retries with exponential backoff. Dead letter queues for failed events.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Activity className="w-10 h-10 text-slate-900 mb-4" />
                <CardTitle>Full Visibility</CardTitle>
                <CardDescription>
                  Real-time delivery status, detailed logs, and webhook replay functionality.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Webhook className="w-10 h-10 text-slate-900 mb-4" />
                <CardTitle>Transform & Route</CardTitle>
                <CardDescription>
                  Transform JSON payloads, filter fields, and route to multiple destinations.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </section>

        {/* Code Example */}
        <section id="docs" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold mb-6">Send Webhooks in Minutes</h2>
              <p className="text-lg text-slate-600 mb-8">
                Just POST your data to your HookFlow endpoint. We handle the rest—retry logic,
                dead letter queues, and delivery tracking included.
              </p>
              <ul className="space-y-3">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Automatic HMAC signature verification</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Idempotency key support</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Rate limiting per app</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Real-time delivery status</span>
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <CodeBlock
                code={`curl -X POST ${API_BASE}/webhook/YOUR_APP_ID \\
  -H "Content-Type: application/json" \\
  -H "X-Webhook-Signature: sha256=..." \\
  -d '{
    "event": "user.created",
    "user_id": "12345",
    "email": "user@example.com"
  }'`}
              />
              <p className="text-sm text-slate-500 text-center">
                Returns 202 Accepted - processed asynchronously
              </p>
            </div>
          </div>
        </section>

        {/* Pricing Preview */}
        <section className="bg-slate-900 text-white py-24">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-bold text-center mb-12">Simple, Transparent Pricing</h2>
            <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
              <div className="bg-slate-800 rounded-lg p-8">
                <h3 className="text-xl font-semibold mb-2">Free</h3>
                <div className="text-4xl font-bold mb-4">$0<span className="text-lg font-normal">/mo</span></div>
                <ul className="space-y-2 text-slate-300 mb-8">
                  <li>1,000 events/month</li>
                  <li>24-hour retention</li>
                  <li>Basic forwarding</li>
                  <li>Community support</li>
                </ul>
                <Button variant="outline" className="w-full" onClick={() => setDialogOpen(true)}>
                  Start Free
                </Button>
              </div>

              <div className="bg-white text-slate-900 rounded-lg p-8 scale-105">
                <div className="text-sm font-semibold text-blue-600 mb-2">Most Popular</div>
                <h3 className="text-xl font-semibold mb-2">Pro</h3>
                <div className="text-4xl font-bold mb-4">$29<span className="text-lg font-normal">/mo</span></div>
                <ul className="space-y-2 text-slate-600 mb-8">
                  <li>100,000 events/month</li>
                  <li>30-day retention</li>
                  <li>All integrations</li>
                  <li>Event replay</li>
                  <li>Email support</li>
                </ul>
                <Button className="w-full" onClick={() => setDialogOpen(true)}>
                  Get Started
                </Button>
              </div>

              <div className="bg-slate-800 rounded-lg p-8">
                <h3 className="text-xl font-semibold mb-2">Team</h3>
                <div className="text-4xl font-bold mb-4">$99<span className="text-lg font-normal">/mo</span></div>
                <ul className="space-y-2 text-slate-300 mb-8">
                  <li>500,000 events/month</li>
                  <li>90-day retention</li>
                  <li>Team members</li>
                  <li>SSO</li>
                  <li>Priority support</li>
                </ul>
                <Button variant="outline" className="w-full" onClick={() => setDialogOpen(true)}>
                  Contact Sales
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-slate-500 text-sm">
          <p>&copy; 2026 HookFlow. Webhook infrastructure for everyone.</p>
        </div>
      </footer>

      {/* Create App Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          {step === "form" ? (
            <>
              <DialogHeader>
                <DialogTitle>Create New App</DialogTitle>
                <DialogDescription>
                  Give your app a name to get started with webhooks.
                </DialogDescription>
              </DialogHeader>

              <DialogBody>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label htmlFor="app-name" className="text-sm font-medium">
                      App Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="app-name"
                      type="text"
                      value={appName}
                      onChange={(e) => setAppName(e.target.value)}
                      placeholder="My Awesome App"
                      className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
                      autoFocus
                    />
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="app-description" className="text-sm font-medium">
                      Description <span className="text-slate-400">(optional)</span>
                    </label>
                    <textarea
                      id="app-description"
                      value={appDescription}
                      onChange={(e) => setAppDescription(e.target.value)}
                      placeholder="What does this app do?"
                      rows={2}
                      className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent resize-none"
                    />
                  </div>

                  {error && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-sm text-red-600">{error}</p>
                    </div>
                  )}
                </div>
              </DialogBody>

              <DialogFooter>
                <Button variant="outline" onClick={handleClose} disabled={loading}>
                  Cancel
                </Button>
                <Button onClick={handleCreateApp} disabled={loading}>
                  {loading ? "Creating..." : "Create App"}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-100 text-green-600">
                    <Check className="h-4 w-4" />
                  </span>
                  App Created!
                </DialogTitle>
                <DialogDescription>
                  Save your secret now - you won't see it again.
                </DialogDescription>
              </DialogHeader>

              <DialogBody>
                <div className="space-y-3">
                  {/* App info */}
                  <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                    <p className="text-sm font-medium text-green-900">{createdApp?.name}</p>
                    <p className="text-xs text-green-700">Ready to receive webhooks</p>
                  </div>

                  {/* Webhook URL */}
                  <div className="space-y-1">
                    <label className="text-xs font-medium flex items-center justify-between">
                      <span>Webhook URL</span>
                      <button
                        onClick={() => createdApp && copyToClipboard(createdApp.webhook_url)}
                        className="text-slate-500 hover:text-slate-700"
                      >
                        {copied ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
                      </button>
                    </label>
                    <code className="block px-2 py-1.5 bg-slate-100 rounded text-xs text-slate-700 break-all">
                      {createdApp?.webhook_url}
                    </code>
                  </div>

                  {/* Webhook Secret */}
                  <div className="space-y-1">
                    <label className="text-xs font-medium flex items-center justify-between">
                      <span className="text-red-500">Webhook Secret *</span>
                      <button
                        onClick={() => createdApp && copyToClipboard(createdApp.webhook_secret)}
                        className="text-slate-500 hover:text-slate-700"
                      >
                        {copied ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
                      </button>
                    </label>
                    <code className="block px-2 py-1.5 bg-amber-50 border border-amber-200 rounded text-xs text-slate-700 break-all font-mono">
                      {createdApp?.webhook_secret}
                    </code>
                    <p className="text-xs text-amber-600">Copy this now - it won't be shown again</p>
                  </div>
                </div>
              </DialogBody>

              <DialogFooter>
                <Button onClick={handleClose}>
                  Done, I've Saved It
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
