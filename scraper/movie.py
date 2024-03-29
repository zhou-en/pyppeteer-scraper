import asyncio
import platform
import sys
import os

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

# BROWSER_PATH = "/Applications/Chromium.app/Contents/MacOS/Chromium"
BROWSER_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
if platform.system() != "Darwin":
    BROWSER_PATH = "/usr/bin/chromium"
    if "/home/pi/Projects/pyppeteer-scraper" not in sys.path:
        sys.path.append("/home/pi/Projects/pyppeteer-scraper")

from datetime import datetime

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

from service.alert import (
    send_slack_message,
    get_last_alert_date,
    update_last_alert_date,
)

log = my_logger.CustomLogger("movie", verbose=True, log_dir="logs")
TARGET_SITE = "https://www.1377x.to/popular-movies"


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
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.4963.0 Safari/537.36",
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.goto(url)

        # wait for specific time
        await self.page.waitFor(10000)
        # wait for element to appear
        # await self.page.waitForSelector(
        #     'span[data-title*="Kids Workshops"]', {"visible": True}
        # )

        # click a button
        # link = await self.page.querySelector('span[data-title*="Kids Workshops"]')
        # await link.click()
        # await self.page.waitFor(5000)

    async def extract_many(self, selector: str, attr: str) -> list:
        """
        Select and return a list of elements using queryAll
        :param selector:
        :param attr:
        :return:
        """
        result = []
        elements = await self.page.querySelectorAll(selector)
        for element in elements:
            text = await element.getProperty(attr)
            result.append(await text.jsonValue())
        return result

    async def extract_one(self, selector: str, attr: str) -> str:
        """
        Locate a single element using querySelector
        :param selector:
        :param attr:
        :return:
        """
        element = await self.page.querySelector(selector)
        text = await element.getProperty(attr)
        return await text.jsonValue()


async def run(proxy: str = None, port: int = None) -> None:
    # define launch option
    launch_options = {
        "options": {
            "headless": False,
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

    log.info(f"Navigate to: {TARGET_SITE}")
    await scraper.goto(TARGET_SITE)

    log.info("Start scraping movies...")

    movies = await scraper.page.querySelectorAll("tbody tr")
    current_year = datetime.utcnow().year
    log.info(f"{len(movies)} events found")
    for movie in movies:
        title_elem = await movie.querySelector("td.name")
        title = await title_elem.getProperty("textContent")
        title_str = await title.jsonValue()
        if current_year in title_str:
            log.info(f"Found movie: {title_str}")
    #     status_elem = await workshop.querySelector("button")
    #     status = await status_elem.getProperty("textContent")
    #     status_str = await status.jsonValue()
    #     start_elem = await workshop.querySelector("p")
    #     start = await start_elem.getProperty("textContent")
    #     start_str = await start.jsonValue()
    #     log.info(f"Found event: {title_str}, status: {status_str}")
    #     if "full" in status_str.lower() or "closed" in status_str.lower():
    #         continue
    #     shop = {"title": title_str, "start": start_str, "status": status_str}
    #     if "register" in status_str.lower():
    #         log.info(
    #             f"{title_str} is open for registration: {status_str}, sending alert..."
    #         )
    #         send_alert(shop, TARGET_SITE)
    await scraper.browser.close()


def send_alert(workshop: dict, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    title = workshop.get("title")
    start = workshop.get("start")
    msg = f'@En "{title}" on {start} is open for registration: {link}'

    # get last alert date
    alert_date = get_last_alert_date("home_depo")
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date("home_depo", current_date)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
