import { NextRequest, NextResponse } from "next/server"
import { auth } from "@/auth"

const GITHUB_REPO = "zhou-en/pyppeteer-scraper"

const WORKFLOW_MAP: Record<string, string> = {
  canada_ircc: "ircc-scraper.yml",
  home_depo: "homedepot-scraper.yml",
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const { id } = await params
  const workflow = WORKFLOW_MAP[id]
  if (!workflow) {
    return NextResponse.json({ error: "Unknown scraper" }, { status: 404 })
  }

  const res = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  )

  if (!res.ok && res.status !== 204) {
    const text = await res.text()
    return NextResponse.json({ error: text }, { status: 502 })
  }

  return NextResponse.json({ ok: true })
}
