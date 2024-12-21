import asyncio
import os
import platform
import sys
from datetime import datetime

from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

load_dotenv()
BROWSER_PATH = os.environ.get("BROWSER_PATH")
if platform.system() != "Darwin":
    sys_paths = ",".join(sys.path)
    if (
        "/home/pi/Projects/pyppeteer-scraper" not in sys_paths
        and "/home/pi" in sys_paths
    ):
        sys.path.append("/home/pi/Projects/pyppeteer-scraper")

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

from service.alert import (
    send_slack_message,
    get_last_alert_date,
    update_last_alert_date,
)

SCRAPER_NAME = "stonebridge_event"

log = my_logger.CustomLogger(SCRAPER_NAME, verbose=True, log_dir="logs")


nest_asyncio.apply()


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
            "executablePath": BROWSER_PATH,
        },
    }

    # Initialize the new scraper
    scraper = Scraper(launch_options)
    target_url = "https://www.ourstonebridge.ca/"

    log.info(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    log.info("Start Stonebridge events...")

    event_elements = await scraper.page.querySelectorAll("#menu-item-2452 li")
    for event in event_elements:
        title_elem = await event.querySelector("a")
        title = await title_elem.getProperty("textContent")
        title_str = await title.jsonValue()
        log.info(f"Going through event: {title_str}")

        if "2025" in title_str:
            # if "summer" in title_str.lower() or "winter" in title_str.lower() or "fall" in title_str.lower():
            if (
                    "soccer" in title_str.lower() or "basketball" in title_str.lower()) and "kinder" not in title_str.lower():
                log.info(f"Found potential events: {title_str}")
                event_found = {"title": title_str, "start": "", "status": ""}
                send_stonebridge_event_alert(event_found, target_url)
                break
    await scraper.browser.close()


def send_stonebridge_event_alert(workshop: dict, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    title = workshop.get("title")
    msg = f"*<{link}|{title}>* is open for registration: {link}"

    # get last alert date
    alert_date = get_last_alert_date(SCRAPER_NAME)
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date(SCRAPER_NAME, current_date)
    else:
        log.info("No alerts are needed!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
