"""
Canada IRCC "Check processing times" scraper.

Polls a single hardcoded application config (Economic immigration → Provincial
Nominees → Yes via Express Entry → Yes → 2023 April) on the canada.ca page
and posts a Slack status card *only when the result changes*.

Run via cron (daily is plenty — IRCC updates monthly).
"""

import asyncio
import json
import os
import platform
import sys

from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

load_dotenv()

BROWSER_PATH = os.environ.get("BROWSER_PATH")
if platform.system() != "Darwin":
    if (
        "/home/pi/Projects/pyppeteer-scraper" not in sys.path
        and "/home/pi" in ",".join(sys.path)
    ):
        sys.path.append("/home/pi/Projects/pyppeteer-scraper")

from service.alert import send_api_error_alert, send_ircc_status_card

log = my_logger.CustomLogger("canada_ircc", verbose=True, log_dir="logs")


SCRAPER_NAME = "canada_ircc"
TARGET_URL = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/services/"
    "application/check-processing-times.html"
)
CONFIG = {
    "application_type": "Economic immigration",
    "economic_class": "Provincial Nominees",
    "online_express_entry": "Yes, via Express Entry",
    "have_applied": "Yes",
    "year": "2023",
    "month": "April",
}
CONFIG_LABEL = "Provincial Nominees · Online via Express Entry"
STATE_FILE = "storage/canada_ircc_state.json"


def load_state() -> dict | None:
    """Return the last cached result dict, or None if no state file yet."""
    if not os.path.exists(STATE_FILE) or os.path.getsize(STATE_FILE) == 0:
        return None
    try:
        with open(STATE_FILE, "r") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        log.warning(f"State file {STATE_FILE} is corrupt; treating as empty")
        return None


def save_state(state: dict) -> None:
    """Atomically write state to STATE_FILE."""
    os.makedirs("storage", exist_ok=True)
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp_path, STATE_FILE)


def has_changed(current: dict, cached: dict | None) -> bool:
    """True when any of the four tracked fields differ (or cached is None)."""
    return cached != current


async def fill_form_and_get_result(page) -> dict:
    """Fill the 5-step form and parse the result block. Returns the 4 raw fields."""
    log.info(f"Navigating to {TARGET_URL}")
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

    log.info("Filling form")
    await page.get_by_label("Select an application type.").select_option(
        label=CONFIG["application_type"]
    )
    await page.get_by_label("Which economic class application?").select_option(
        label=CONFIG["economic_class"]
    )
    await page.get_by_label("Online via Express Entry?").select_option(
        label=CONFIG["online_express_entry"]
    )
    await page.get_by_label("Have you already applied?").select_option(
        label=CONFIG["have_applied"]
    )
    await page.get_by_label("Year (YYYY)").fill(CONFIG["year"])
    await page.get_by_label("Month").select_option(label=CONFIG["month"])

    log.info("Submitting form")
    await page.get_by_role("button", name="Get processing time").click()

    await page.wait_for_selector("text=Estimated time left", timeout=15000)

    estimated_time = (
        await page.locator(":text('Estimated time left')")
        .locator("..")
        .locator("h3, h4, p")
        .first.inner_text()
    )
    estimated_time = estimated_time.strip()

    last_updated_raw = await page.locator(
        ":text-matches('Last updated:', 'i')"
    ).first.inner_text()
    last_updated = last_updated_raw.replace("Last updated:", "").strip()

    people_ahead = (
        await page.locator(":text('People ahead of you')")
        .locator("..")
        .locator("p, div")
        .first.inner_text()
    )
    people_ahead = people_ahead.strip()

    total_waiting = (
        await page.locator(
            ":text('Total number of people waiting for a decision')"
        )
        .locator("..")
        .locator("p, div")
        .first.inner_text()
    )
    total_waiting = total_waiting.strip()

    return {
        "estimated_time": estimated_time,
        "last_updated": last_updated,
        "people_ahead": people_ahead,
        "total_waiting": total_waiting,
    }


async def run() -> None:
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as playwright:
            launch_kwargs = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-notifications",
                ],
            }
            if BROWSER_PATH:
                launch_kwargs["executable_path"] = BROWSER_PATH

            browser = await playwright.chromium.launch(**launch_kwargs)
            try:
                page = await browser.new_page(
                    viewport={"width": 1920, "height": 1080}
                )
                current = await fill_form_and_get_result(page)
            finally:
                await browser.close()
    except Exception as e:
        log.error(f"Scraper failed: {e}", exc_info=True)
        send_api_error_alert(
            "Canada IRCC",
            "Scraper failed before producing a result",
            f"Error: {str(e)}\nURL: {TARGET_URL}",
        )
        sys.exit(1)

    log.info(f"Parsed result: {current}")

    cached = load_state()
    if not has_changed(current, cached):
        log.info("No change since last run — skipping Slack notification")
        return

    log.info(f"Change detected (cached={cached}) — posting status card")
    send_ircc_status_card(
        config_label=CONFIG_LABEL,
        estimated_time=current["estimated_time"],
        people_ahead=current["people_ahead"],
        total_waiting=current["total_waiting"],
        last_updated=current["last_updated"],
        source_url=TARGET_URL,
    )
    save_state(current)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
