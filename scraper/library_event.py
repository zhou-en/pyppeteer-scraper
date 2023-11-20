import asyncio
import platform
import sys

if platform.system() != "Darwin":
    if "/home/pi/Projects/pyppeteer-scraper" not in sys.path:
        sys.path.append("/home/pi/Projects/pyppeteer-scraper")
from datetime import datetime, timedelta

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

from my_logger import CustomLogger
from service.alert import (
    send_slack_message,
    get_last_alert_date,
    update_last_alert_date,
)

SCRAPER_NAME = "library_event"

log = CustomLogger(SCRAPER_NAME, verbose=True, log_dir="logs")


nest_asyncio.apply()

MAP_DATA = "data=!3m1!4b1!4m6!3m5!1s0x5304f126678f6d21:0x6286d8c943291d12!8m2!3d52.108115!4d-106.6507629!16s%2Fg%2F12hsmwdl7?entry=ttu"


class Scraper:
    def __init__(self, launch_options: dict) -> None:
        self.page = None
        self.browser = None
        self.options = launch_options.get("options")
        self.viewPort = launch_options.get("viewPort")

    async def goto(self, url: str) -> None:
        self.browser = await launch(options=self.options)
        self.page = await self.browser.newPage()
        await self.page.setUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.goto(url)

        # wait for specific time
        await self.page.waitFor(5000)


async def run(proxy: str = None, port: int = None) -> None:
    # define launch option
    launch_options = {
        "options": {
            "headless": True,
            # "timeout": 50000,
            "autoClose": False,
            "args": [
                "--no-sandbox",
                "--disable-notifications",
                "--start-maximized",
                # "--window-size=1920,1080"
            ],
            "ignoreDefaultArgs": ["--disable-extensions", "--enable-automation"],
            "defaultViewport": {"width": 1600, "height": 900},
        },

    }

    # Initialize the new scraper
    scraper = Scraper(launch_options)

    # Navigate to the target
    location = "3090"  # Round Prairie Library
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=180)).date().strftime("%Y-%m-%d")
    keywords = "code+club"
    target_url = f"https://saskatoonlibrary.ca/events-guide/results/?startDate={start_date}&endDate={end_date}&ages=all&locations={location}&types=all&keyword={keywords}"

    log.info(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    log.info("Start scraping library events...")

    event_elements = await scraper.page.querySelectorAll("div.day-event-card")
    for event in event_elements:

        title_elem = await event.querySelector("h3")
        title = await title_elem.getProperty("textContent")
        title_str = await title.jsonValue()

        status_elem = await event.querySelector("div.card-reg")
        status = await status_elem.getProperty("textContent")
        status_str = await status.jsonValue()

        dow_elem = await event.querySelector("span.event-dow")
        dow = await dow_elem.getProperty("textContent")
        dow_str = await dow.jsonValue()

        event_date_elem = await event.querySelector("span.event-date")
        event_date = await event_date_elem.getProperty("textContent")
        event_date_str = await event_date.jsonValue()

        event_month_elem = await event.querySelector("span.event-month")
        event_month = await event_month_elem.getProperty("textContent")
        event_month_str = await event_month.jsonValue()

        try:
            event_month_int = int(event_month_str)
            event_month_str = event_month_int + 1
        except Exception as err:
            log.error(f"Failed to convert month of {event_month_str} to 1-based")

        start_str = f"{event_month_str}-{event_date_str}, {dow_str}"

        log.info(f"{title_str} starts on {start_str}: {status_str}")
        if "full" in status_str.lower() or "closed" in status_str.lower():
            continue
        else:
            log.info(f"{title_str} is open for registration: {status_str}")
            reg_elem = await event.querySelector("div[class='card-reg future'")
            reg_details = await reg_elem.getProperty("textContent")
            reg_details_str = await reg_details.jsonValue()

            location_elem = await event.querySelector("strong")
            location_details = await location_elem.getProperty("textContent")
            location_str = await location_details.jsonValue()
            location_link = f"[{location_str}](https://www.google.com/maps/place/{location_str.replace(' ', '+')}/{MAP_DATA})"

            event_detail = f"{reg_details_str} at {location_link}"
            event_found = {"title": title_str, "start": start_str, "status": event_detail}
            send_library_event_alert(event_found, target_url)
            break
    await scraper.browser.close()


def send_library_event_alert(workshop: dict, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    title = workshop.get("title")
    start = workshop.get("start")
    status = workshop.get("status")
    msg = f'@En "{title}" {status} starting on {start} is open for registration: {link}'

    # get last alert date
    alert_date = get_last_alert_date(SCRAPER_NAME)
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date(SCRAPER_NAME, current_date)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
