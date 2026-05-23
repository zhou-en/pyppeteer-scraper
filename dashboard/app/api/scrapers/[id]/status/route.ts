import { NextRequest, NextResponse } from "next/server"
import { auth } from "@/auth"
import { getScraper } from "@/lib/db"

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const { id } = await params
  const scraper = await getScraper(id)
  if (!scraper) return NextResponse.json({ error: "Not found" }, { status: 404 })

  return NextResponse.json({
    last_run_at: scraper.last_run_at,
    last_run_status: scraper.last_run_status,
    last_run_duration_ms: scraper.last_run_duration_ms,
    last_run_message: scraper.last_run_message,
  })
}
