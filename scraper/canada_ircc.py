"""
Canada IRCC "Check processing times" scraper.

Polls a single hardcoded application config (Economic immigration → Provincial
Nominees → Yes via Express Entry → Yes → 2023 April) on the canada.ca page
and posts a Slack status card *only when the result changes*.

Run via cron (daily is plenty — IRCC updates monthly).
"""

import os
import platform
import sys
import time

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


def _get_db_conn():
    import psycopg2
    url = os.environ.get("POSTGRES_URL", "")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)


def is_active() -> bool:
    """Return False if the scraper has been deactivated in the dashboard."""
    try:
        conn = _get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM scrapers WHERE id = %s", (SCRAPER_NAME,))
        row = cur.fetchone()
        conn.close()
        return bool(row[0]) if row else True
    except Exception as e:
        log.warning(f"Could not check is_active flag: {e} — defaulting to active")
        return True


def load_state() -> dict | None:
    """Return the last cached result from Neon, or None if no state yet."""
    try:
        conn = _get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT estimated_time, last_updated, people_ahead, total_waiting "
            "FROM ircc_state WHERE id = 1"
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "estimated_time": row[0],
            "last_updated": row[1],
            "people_ahead": row[2],
            "total_waiting": row[3],
        }
    except Exception as e:
        log.warning(f"Could not load state from DB: {e} — treating as empty")
        return None


def save_state(state: dict) -> None:
    """Upsert the current result into ircc_state."""
    conn = _get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ircc_state (id, estimated_time, last_updated, people_ahead, total_waiting, scraped_at)
        VALUES (1, %s, %s, %s, %s, NOW())
        ON CONFLICT (id) DO UPDATE SET
            estimated_time = EXCLUDED.estimated_time,
            last_updated   = EXCLUDED.last_updated,
            people_ahead   = EXCLUDED.people_ahead,
            total_waiting  = EXCLUDED.total_waiting,
            scraped_at     = EXCLUDED.scraped_at
        """,
        (state["estimated_time"], state["last_updated"],
         state["people_ahead"], state["total_waiting"]),
    )
    conn.commit()
    conn.close()


def write_run_log(started_at: float, status: str, message: str) -> None:
    """Write a run entry to scraper_runs and update scrapers.last_run_*."""
    duration_ms = int((time.time() - started_at) * 1000)
    try:
        conn = _get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO scraper_runs (scraper_id, started_at, duration_ms, status, message)
            VALUES (%s, to_timestamp(%s), %s, %s, %s)
            """,
            (SCRAPER_NAME, started_at, duration_ms, status, message[:500]),
        )
        cur.execute(
            """
            UPDATE scrapers SET
                last_run_at = to_timestamp(%s),
                last_run_duration_ms = %s,
                last_run_status = %s,
                last_run_message = %s
            WHERE id = %s
            """,
            (started_at, duration_ms, status, message[:500], SCRAPER_NAME),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Could not write run log: {e}")


def has_changed(current: dict, cached: dict | None) -> bool:
    """True when any of the four tracked fields differ (or cached is None)."""
    return cached != current


PTIME_URL = "https://www.canada.ca/content/dam/ircc/documents/json/data-ptime-non-country-en.json"
FLPT_URL  = "https://www.canada.ca/content/dam/ircc/documents/json/flpt-en.json"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch_ircc_data() -> dict:
    """Fetch processing times directly from the two IRCC JSON endpoints."""
    import urllib.request as _req
    import json as _json

    def _get(url):
        r = _req.Request(url, headers={"User-Agent": _UA, "Referer": TARGET_URL})
        with _req.urlopen(r, timeout=30) as resp:
            return _json.load(resp)

    ptime = _get(PTIME_URL)
    flpt  = _get(FLPT_URL)

    estimated_time = ptime.get("pnp_ee_flpt", {}).get("pnp_ee_flpt", "—")
    last_updated   = ptime.get("default-update", {}).get("lastupdated", "—")
    total_waiting  = flpt.get("total-people", {}).get("pnp-ee", "—")
    people_ahead   = total_waiting  # same figure; page shows both labels for it

    log.info(
        f"Fetched: estimated_time={estimated_time!r}, last_updated={last_updated!r}, "
        f"total_waiting={total_waiting!r}"
    )
    return {
        "estimated_time": estimated_time,
        "last_updated": last_updated,
        "people_ahead": people_ahead,
        "total_waiting": total_waiting,
    }


def run() -> None:
    started_at = time.time()

    if not is_active():
        log.info("Scraper is deactivated — skipping run")
        write_run_log(started_at, "skipped", "deactivated")
        return

    try:
        result = fetch_ircc_data()
    except Exception as e:
        log.error(f"Scraper failed: {e}", exc_info=True)
        send_api_error_alert(
            "Canada IRCC",
            "Scraper failed before producing a result",
            f"Error: {str(e)}\nURL: {TARGET_URL}",
        )
        write_run_log(started_at, "fail", str(e))
        sys.exit(1)

    log.info(f"Parsed result: {result}")

    cached = load_state()
    if not has_changed(result, cached):
        log.info("No change since last run — skipping Slack notification")
        write_run_log(started_at, "success", "no change")
        return

    log.info(f"Change detected (cached={cached}) — posting status card")
    send_ircc_status_card(
        config_label=CONFIG_LABEL,
        estimated_time=result["estimated_time"],
        people_ahead=result["people_ahead"],
        total_waiting=result["total_waiting"],
        last_updated=result["last_updated"],
        source_url=TARGET_URL,
    )
    save_state(result)
    write_run_log(started_at, "success", "state changed")


if __name__ == "__main__":
    run()
