"use client"

import { ClerkProvider } from "@clerk/clerk-react"
import { ReactNode } from "react"

const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

if (!clerkPublishableKey) {
  // For development, allow missing key
  console.warn("Missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
}

interface ClerkProviderWrapperProps {
  children: ReactNode
}

export function ClerkProviderWrapper({ children }: ClerkProviderWrapperProps) {
  return (
    <ClerkProvider
      publishableKey={clerkPublishableKey || "pk_test_dummy"}
      appearance={{
        elements: {
          formButtonPrimary: "backgroundColor: #3b82f6",
          footerActionLink: "color: #3b82f6",
        },
      }}
    >
      {children}
    </ClerkProvider>
  )
}
