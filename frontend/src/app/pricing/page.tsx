"use client"

import { Check } from "lucide-react"
import { Button } from "@/components/ui/button"

const plans = [
  {
    name: "Free",
    tier: "free",
    price: 0,
    description: "Perfect for getting started",
    features: [
      { name: "1,000 webhooks/month", included: true },
      { name: "7-day data retention", included: true },
      { name: "1 destination", included: true },
      { name: "3 retry attempts", included: true },
      { name: "Email support", included: true },
      { name: "Custom retry settings", included: false },
      { name: "Longer retention", included: false },
      { name: "Priority support", included: false },
    ],
    cta: "Get Started",
  },
  {
    name: "Pro",
    tier: "pro",
    price: 29,
    description: "For growing applications",
    features: [
      { name: "50,000 webhooks/month", included: true },
      { name: "30-day data retention", included: true },
      { name: "10 destinations", included: true },
      { name: "5 retry attempts", included: true },
      { name: "Email support", included: true },
      { name: "Custom retry settings", included: true },
      { name: "Advanced analytics", included: true },
      { name: "Priority support", included: false },
    ],
    cta: "Upgrade to Pro",
    highlighted: true,
  },
  {
    name: "Team",
    tier: "team",
    price: 99,
    description: "For teams with high volume",
    features: [
      { name: "500,000 webhooks/month", included: true },
      { name: "90-day data retention", included: true },
      { name: "50 destinations", included: true },
      { name: "10 retry attempts", included: true },
      { name: "Priority email support", included: true },
      { name: "Custom retry settings", included: true },
      { name: "Advanced analytics", included: true },
      { name: "Team collaboration", included: true },
    ],
    cta: "Upgrade to Team",
  },
  {
    name: "Enterprise",
    tier: "enterprise",
    price: null,
    description: "For large-scale operations",
    features: [
      { name: "Unlimited webhooks", included: true },
      { name: "365-day data retention", included: true },
      { name: "Unlimited destinations", included: true },
      { name: "Unlimited retries", included: true },
      { name: "24/7 dedicated support", included: true },
      { name: "Custom retry settings", included: true },
      { name: "Advanced analytics", included: true },
      { name: "Custom integrations", included: true },
    ],
    cta: "Contact Sales",
  },
]

export default function PricingPage() {
  const handleSubscribe = async (tier: string) => {
    if (tier === "enterprise") {
      // Open contact form or mailto
      window.location.href = "mailto:sales@hookflow.dev"
      return
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/billing/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Clerk handles the auth token automatically via middleware
        },
        credentials: "include",
        body: JSON.stringify({
          price_id: process.env[`NEXT_PUBLIC_PRICE_${tier.toUpperCase()}`],
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to create checkout session")
      }

      const { url } = await response.json()
      window.location.href = url
    } catch (error) {
      console.error("Checkout error:", error)
      alert("Failed to proceed to checkout. Please try again.")
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Simple, Transparent Pricing</h1>
          <p className="text-lg text-gray-600">Start free, scale as you grow</p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {plans.map((plan) => (
            <div
              key={plan.tier}
              className={`bg-white rounded-2xl shadow-sm border-2 transition-all ${
                plan.highlighted
                  ? "border-blue-600 shadow-lg scale-105"
                  : "border-gray-200"
              }`}
            >
              {plan.highlighted && (
                <div className="bg-blue-600 text-white text-sm font-medium py-1 px-3 rounded-t-xl text-center">
                  Most Popular
                </div>
              )}
              <div className="p-6">
                <h3 className="text-xl font-semibold text-gray-900">{plan.name}</h3>
                <p className="text-sm text-gray-500 mt-1">{plan.description}</p>
                <div className="mt-4">
                  {plan.price !== null ? (
                    <div className="flex items-baseline">
                      <span className="text-4xl font-bold text-gray-900">${plan.price}</span>
                      <span className="text-gray-500 ml-1">/month</span>
                    </div>
                  ) : (
                    <div className="text-2xl font-bold text-gray-900">Custom</div>
                  )}
                </div>
                <ul className="mt-6 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature.name} className="flex items-start">
                      {feature.included ? (
                        <Check className="h-5 w-5 text-green-500 shrink-0" />
                      ) : (
                        <div className="h-5 w-5 text-gray-300 shrink-0">✕</div>
                      )}
                      <span className={`ml-3 text-sm ${feature.included ? "text-gray-700" : "text-gray-400"}`}>
                        {feature.name}
                      </span>
                    </li>
                  ))}
                </ul>
                <Button
                  onClick={() => handleSubscribe(plan.tier)}
                  className={`w-full mt-6 ${
                    plan.highlighted
                      ? "bg-blue-600 hover:bg-blue-700"
                      : "bg-gray-100 hover:bg-gray-200 text-gray-900"
                  }`}
                >
                  {plan.cta}
                </Button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center text-sm text-gray-500">
          <p>All plans include webhook replay, real-time delivery, and event filtering.</p>
          <p className="mt-2">Need a custom plan? <a href="mailto:sales@hookflow.dev" className="text-blue-600 hover:underline">Contact us</a></p>
        </div>
      </div>
    </div>
  )
}
