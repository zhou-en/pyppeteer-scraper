"use client"

import { useState, useEffect, useRef } from "react"
import type { Scraper, IrccState, ScraperStatus } from "@/lib/db"
import { IrccData } from "@/components/ircc-data"

const WORKFLOW_URLS: Record<string, string> = {
  canada_ircc: "https://github.com/zhou-en/pyppeteer-scraper/actions/workflows/ircc-scraper.yml",
  home_depo: "https://github.com/zhou-en/pyppeteer-scraper/actions/workflows/homedepot-scraper.yml",
}

function nextRunTime(cronSchedule: string): string {
  const parts = cronSchedule.split(" ")
  if (parts.length < 2) return "Scheduled"
  const [minute, hour] = parts

  // Hourly schedule (hour = "*"): next occurrence at :MM of the next/current hour
  if (hour === "*") {
    const min = parseInt(minute, 10) || 0
    const now = new Date()
    const next = new Date()
    next.setMinutes(min, 0, 0)
    if (next <= now) next.setHours(next.getHours() + 1, min, 0, 0)
    return next.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
  }

  // Simple fixed hour (e.g. "0 15 * * *" or "0 15 * * 1-5")
  const hourNum = parseInt(hour, 10)
  if (!isNaN(hourNum)) {
    const now = new Date()
    const next = new Date()
    next.setUTCHours(hourNum, 0, 0, 0)
    if (next <= now) next.setUTCDate(next.getUTCDate() + 1)
    return next.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
  }

  return "Scheduled"
}

function StatusDot({ status }: { status: string | null }) {
  if (!status) return <span className="w-2 h-2 rounded-full bg-zinc-600 inline-block" />
  if (status === "success") return <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
  if (status === "skipped") return <span className="w-2 h-2 rounded-full bg-zinc-500 inline-block" />
  return <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
}

function StatusLabel({ status }: { status: string | null }) {
  if (!status) return <span className="text-zinc-500">Never run</span>
  if (status === "success") return <span className="text-emerald-400">Success</span>
  if (status === "skipped") return <span className="text-zinc-400">Skipped</span>
  return <span className="text-red-400">Failed</span>
}

export function ScraperCard({
  scraper,
  irccState,
}: {
  scraper: Scraper
  irccState?: IrccState | null
}) {
  const [isActive, setIsActive] = useState(scraper.is_active)
  const [triggering, setTriggering] = useState(false)
  const [toggleLoading, setToggleLoading] = useState(false)

  // Run monitoring state
  const [runState, setRunState] = useState<
    | { phase: "idle" }
    | { phase: "running"; dispatchedAt: number }
    | { phase: "done"; status: ScraperStatus; durationMs: number | null; message: string | null }
  >({ phase: "idle" })
  const [elapsed, setElapsed] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Elapsed timer while running
  useEffect(() => {
    if (runState.phase !== "running") return
    setElapsed(0)
    elapsedRef.current = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current) }
  }, [runState.phase])

  // Poll DB every 5s after dispatch
  useEffect(() => {
    if (runState.phase !== "running") return
    const { dispatchedAt } = runState

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/scrapers/${scraper.id}/status`)
        if (!res.ok) return
        const data = await res.json()
        if (!data.last_run_at) return
        const ranAt = new Date(data.last_run_at).getTime()
        if (ranAt >= dispatchedAt) {
          if (pollRef.current) clearInterval(pollRef.current)
          if (elapsedRef.current) clearInterval(elapsedRef.current)
          setRunState({
            phase: "done",
            status: data.last_run_status,
            durationMs: data.last_run_duration_ms,
            message: data.last_run_message,
          })
        }
      } catch { /* ignore transient errors */ }
    }, 5000)

    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [runState, scraper.id])

  async function handleToggle() {
    const next = !isActive
    setToggleLoading(true)
    setIsActive(next)
    await fetch(`/api/scrapers/${scraper.id}/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isActive: next }),
    })
    setToggleLoading(false)
  }

  async function handleRunNow() {
    setTriggering(true)
    const dispatchedAt = Date.now()
    await fetch(`/api/scrapers/${scraper.id}/trigger`, { method: "POST" })
    setTriggering(false)
    setRunState({ phase: "running", dispatchedAt })
  }

  const workflowUrl = WORKFLOW_URLS[scraper.id]

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      {/* Card header */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <StatusDot status={scraper.last_run_status} />
          <h2 className="font-semibold text-zinc-100">{scraper.name}</h2>
          <span className="text-xs text-zinc-500 font-mono">{scraper.id}</span>
        </div>
        {/* Active toggle */}
        <button
          onClick={handleToggle}
          disabled={toggleLoading}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
            isActive ? "bg-emerald-500" : "bg-zinc-700"
          } ${toggleLoading ? "opacity-50" : ""}`}
          aria-label={isActive ? "Deactivate scraper" : "Activate scraper"}
        >
          <span
            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
              isActive ? "translate-x-4" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>

      {/* Card body */}
      <div className="px-6 py-4 space-y-4">
        {scraper.description && (
          <p className="text-sm text-zinc-400">{scraper.description}</p>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium mb-1">Status</p>
            <p className="text-sm font-medium">
              <StatusLabel status={scraper.last_run_status} />
            </p>
          </div>
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium mb-1">Last run</p>
            <p className="text-sm text-zinc-300">
              {scraper.last_run_at
                ? new Date(scraper.last_run_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
                : "Never"}
              {scraper.last_run_duration_ms != null && (
                <span className="text-zinc-500 ml-1">({(scraper.last_run_duration_ms / 1000).toFixed(1)}s)</span>
              )}
            </p>
          </div>
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium mb-1">Next run</p>
            <p className="text-sm text-zinc-300">
              {isActive ? nextRunTime(scraper.cron_schedule) : <span className="text-zinc-600">Inactive</span>}
            </p>
          </div>
        </div>

        {/* Error message */}
        {scraper.last_run_status === "fail" && scraper.last_run_message && (
          <div className="rounded-lg bg-red-950/50 border border-red-900/50 px-4 py-3 text-sm text-red-400 font-mono">
            {scraper.last_run_message}
          </div>
        )}

        {/* IRCC specific data */}
        {scraper.id === "canada_ircc" && irccState && (
          <IrccData state={irccState} />
        )}

        {/* Run status banner */}
        {runState.phase === "running" && (
          <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-zinc-300">
              <svg className="animate-spin w-3.5 h-3.5 text-zinc-400 shrink-0" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Running… {elapsed}s
            </div>
            {workflowUrl && (
              <a href={workflowUrl} target="_blank" rel="noopener noreferrer"
                className="text-xs text-zinc-400 hover:text-zinc-200 underline underline-offset-2 transition-colors">
                View in GitHub Actions →
              </a>
            )}
          </div>
        )}
        {runState.phase === "done" && (
          <div className={`rounded-lg px-4 py-3 flex items-center justify-between border ${
            runState.status === "success"
              ? "bg-emerald-950/50 border-emerald-900/50"
              : "bg-red-950/50 border-red-900/50"
          }`}>
            <div className={`flex items-center gap-2 text-sm ${
              runState.status === "success" ? "text-emerald-400" : "text-red-400"
            }`}>
              {runState.status === "success" ? (
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              <span>
                {runState.status === "success" ? "Completed" : "Failed"}
                {runState.durationMs != null && (
                  <span className="opacity-70 ml-1">in {(runState.durationMs / 1000).toFixed(1)}s</span>
                )}
                {runState.status !== "success" && runState.message && (
                  <span className="ml-2 font-mono text-xs opacity-80">{runState.message}</span>
                )}
              </span>
            </div>
            <button
              onClick={() => setRunState({ phase: "idle" })}
              className="text-xs opacity-50 hover:opacity-100 transition-opacity ml-4"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleRunNow}
            disabled={triggering || runState.phase === "running"}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-600 text-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {triggering ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Triggering…
              </span>
            ) : runState.phase === "running" ? "Running…" : "Run Now"}
          </button>

          <a
            href={`/scrapers/${scraper.id}/logs`}
            className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-all"
          >
            View Logs
          </a>

          {workflowUrl && (
            <a
              href={workflowUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-all"
            >
              GitHub Actions ↗
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
