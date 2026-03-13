import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleString()
}

export function truncate(str: string, len: number = 50): string {
  if (str.length <= len) return str
  return str.slice(0, len) + "..."
}

export function formatJson(obj: unknown): string {
  return JSON.stringify(obj, null, 2)
}
