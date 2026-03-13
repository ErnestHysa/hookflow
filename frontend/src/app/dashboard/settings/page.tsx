"use client"

import Link from "next/link"
import { Settings, CreditCard, User as UserIcon } from "lucide-react"
import { BillingSettings } from "@/components/dashboard/billing-settings"

export default function AccountSettingsPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              ← Back to Dashboard
            </Link>
            <h1 className="text-xl font-semibold">Account Settings</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid md:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="md:col-span-1">
            <nav className="space-y-1">
              <a
                href="#billing"
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg bg-white border hover:bg-gray-50"
              >
                <CreditCard className="w-4 h-4" />
                Billing & Plan
              </a>
              <a
                href="#profile"
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg hover:bg-gray-100"
              >
                <UserIcon className="w-4 h-4" />
                Profile
              </a>
              <a
                href="#account"
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg hover:bg-gray-100"
              >
                <Settings className="w-4 h-4" />
                Account
              </a>
            </nav>
          </div>

          {/* Main Content */}
          <div className="md:col-span-3 space-y-6">
            <section id="billing">
              <BillingSettings />
            </section>

            <section id="profile" className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold mb-4">Profile</h2>
              <p className="text-sm text-gray-500">
                Your profile is managed through our authentication provider.
              </p>
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between py-2 border-b">
                  <span className="text-sm text-gray-600">Email</span>
                  <span className="text-sm font-medium">Manage in Clerk</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b">
                  <span className="text-sm text-gray-600">Password</span>
                  <span className="text-sm font-medium">Manage in Clerk</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">Two-Factor Authentication</span>
                  <span className="text-sm font-medium">Manage in Clerk</span>
                </div>
              </div>
            </section>

            <section id="account" className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold mb-4">Account</h2>
              <p className="text-sm text-gray-500 mb-4">
                Manage your account settings and preferences.
              </p>
              <div className="space-y-4">
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <p className="text-sm font-medium">Email Notifications</p>
                    <p className="text-xs text-gray-500">Receive webhook delivery reports</p>
                  </div>
                  <button className="text-sm text-blue-600 hover:underline">
                    Configure
                  </button>
                </div>
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <p className="text-sm font-medium">API Documentation</p>
                    <p className="text-xs text-gray-500">View API docs and examples</p>
                  </div>
                  <a
                    href="/docs"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    View Docs
                  </a>
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-sm font-medium">Delete Account</p>
                    <p className="text-xs text-gray-500">Permanently delete your account</p>
                  </div>
                  <button className="text-sm text-red-600 hover:underline">
                    Delete
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
