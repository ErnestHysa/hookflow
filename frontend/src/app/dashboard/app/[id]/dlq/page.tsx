"use client"

import { use } from "react"
import { DeadLetterQueue } from "@/components/dashboard/dead-letter-queue"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

interface PageProps {
  params: Promise<{ id: string }>
}

export default function AppDLQPage({ params }: PageProps) {
  const { id } = use(params)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href={`/dashboard/app/${id}`}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Dead Letter Queue</h1>
          <p className="text-gray-500">View and manage failed webhook deliveries</p>
        </div>
      </div>

      <DeadLetterQueue appId={id} />
    </div>
  )
}
