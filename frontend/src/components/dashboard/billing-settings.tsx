"use client"

import { useEffect, useState } from "react"
import { CreditCard, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface SubscriptionStatus {
  status: string
  plan_tier: string
  cancel_at_period_end: boolean
  current_period_end?: number
}

export function BillingSettings() {
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSubscriptionStatus()
  }, [])

  const fetchSubscriptionStatus = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/subscription`, {
        credentials: "include",
      })

      if (response.ok) {
        const data = await response.json()
        setSubscription(data)
      }
    } catch (error) {
      console.error("Failed to fetch subscription:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleManageSubscription = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/billing/portal`, {
        method: "POST",
        credentials: "include",
      })

      if (!response.ok) {
        throw new Error("Failed to create portal session")
      }

      const { url } = await response.json()
      window.location.href = url
    } catch (error) {
      console.error("Portal error:", error)
      alert("Failed to open billing portal. Please try again.")
    }
  }

  const handleUpgrade = () => {
    window.location.href = "/pricing"
  }

  const formatTier = (tier: string) => {
    return tier.charAt(0).toUpperCase() + tier.slice(1)
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  }

  if (loading) {
    return <div className="animate-pulse">Loading billing information...</div>
  }

  const isFree = !subscription || subscription.plan_tier === "free"
  const isActive = subscription && ["active", "trialing"].includes(subscription.status)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="w-5 h-5" />
            Current Plan
          </CardTitle>
          <CardDescription>
            Manage your subscription and billing preferences
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div>
              <p className="font-medium text-lg">
                {formatTier(subscription?.plan_tier || "free")} Plan
              </p>
              <p className="text-sm text-gray-500">
                {isActive ? (
                  subscription?.cancel_at_period_end ? (
                    "Cancels at period end"
                  ) : subscription?.current_period_end ? (
                    `Renews on ${formatDate(subscription.current_period_end)}`
                  ) : (
                    "Active subscription"
                  )
                ) : (
                  "Free tier - no credit card required"
                )}
              </p>
            </div>
            <div className="flex gap-2">
              {isFree ? (
                <Button onClick={handleUpgrade}>
                  Upgrade Plan
                </Button>
              ) : (
                <Button
                  variant="outline"
                  onClick={handleManageSubscription}
                  className="flex items-center gap-2"
                >
                  Manage Billing
                  <ExternalLink className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>

          {subscription && subscription.status === "past_due" && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                <strong>Payment Required:</strong> Your last payment failed. Please update your payment method
                to continue service.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={handleManageSubscription}
                className="mt-2"
              >
                Update Payment Method
              </Button>
            </div>
          )}

          <div className="grid md:grid-cols-3 gap-4 mt-6">
            <div className="p-4 bg-slate-50 rounded-lg">
              <p className="text-sm text-gray-500">Webhooks</p>
              <p className="font-semibold">
                {isFree ? "1,000" : "50,000+"}
                <span className="text-gray-500 font-normal">/month</span>
              </p>
            </div>
            <div className="p-4 bg-slate-50 rounded-lg">
              <p className="text-sm text-gray-500">Retention</p>
              <p className="font-semibold">
                {isFree ? "7" : "30"}
                <span className="text-gray-500 font-normal"> days</span>
              </p>
            </div>
            <div className="p-4 bg-slate-50 rounded-lg">
              <p className="text-sm text-gray-500">Destinations</p>
              <p className="font-semibold">
                {isFree ? "1" : "10"}
                <span className="text-gray-500 font-normal"> max</span>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>
            Manage your payment methods through the billing portal
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isFree ? (
            <p className="text-sm text-gray-500">No payment method required for free tier.</p>
          ) : (
            <Button
              variant="outline"
              onClick={handleManageSubscription}
              className="flex items-center gap-2"
            >
              <CreditCard className="w-4 h-4" />
              Manage Payment Methods
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Billing History</CardTitle>
          <CardDescription>
            View and download your invoices
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            onClick={handleManageSubscription}
            className="flex items-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            View Invoices
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
