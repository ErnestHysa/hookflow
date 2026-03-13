"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Copy, Check } from "lucide-react"

interface CodeBlockProps {
  code: string
  language?: string
  className?: string
}

export function CodeBlock({ code, language = "bash", className }: CodeBlockProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn("relative group", className)}>
      <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleCopy}
          className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-white"
          aria-label="Copy code"
        >
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 rounded-lg bg-slate-900 text-slate-50 text-sm">
        <code>{code}</code>
      </pre>
    </div>
  )
}
