import asyncio
import os
import platform
import sys
import json

from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

load_dotenv()

BROWSER_PATH = os.environ.get("BROWSER_PATH")
if platform.system() != "Darwin":
    if "/home/pi/Projects/pyppeteer-scraper" not in sys.path and "/home/pi" in ",".join(
        sys.path
    ):
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

log = my_logger.CustomLogger("home_depo", verbose=True, log_dir="logs")


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
        await self.page.goto(url, {"waitUntil": "load", "timeout": 600000})

        # # wait for specific time to bypass store selection
        await self.page.waitFor(3000)
        # wait for element to appear
        selector = 'span[data-title*="Kids Workshops"]'
        await self.page.waitForSelector(selector, {"visible": True, "timeout": 600000})

        # close location select modal
        close_btn = await self.page.querySelector("button[class*=acl-reset-button]")
        if close_btn:
            await close_btn.click()
            await self.page.waitFor(5000)

        # click kid diy tab button
        link = await self.page.querySelector(selector)
        await link.click()
        await self.page.waitFor(5000)

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
            "headless": True,
            # "timeout": 50000,
            "autoClose": False,
            "args": [
                "--no-sandbox",
                "--disable-notifications",
                "--start-maximized",
            ],
            "ignoreDefaultArgs": ["--disable-extensions", "--enable-automation"],
            "defaultViewport": {"width": 1920, "height": 1080},
            "executablePath": BROWSER_PATH,
        },
    }

    # Initialize the new scraper
    scraper = Scraper(launch_options)

    # Navigate to the target
    # target_url = "https://www.homedepot.ca/workshops?store=7265"
    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    log.info(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    log.info("Start scraping Kids Workshop...")

    ws_elements = await scraper.page.querySelectorAll("localized-tabs-content > div")
    log.info(f"{len(ws_elements)} events found")
    for workshop in ws_elements:
        title_elem = await workshop.querySelector("h3")
        title = await title_elem.getProperty("textContent")
        title_str = await title.jsonValue()
        status_elem = await workshop.querySelector("button")
        status = await status_elem.getProperty("textContent")
        status_str = await status.jsonValue()
        start_elem = await workshop.querySelector("p")
        start = await start_elem.getProperty("textContent")
        start_str = await start.jsonValue()
        log.info(f"Found event: {title_str}, status: {status_str}")
        if "full" in status_str.lower() or "closed" in status_str.lower():
            log.info("Event is not open for registration!")
            continue
        shop = {"title": title_str, "start": start_str, "status": status_str}
        if "register" in status_str.lower():
            log.info(f"{title_str} is open for registration: {status_str}")
            send_home_depo_alert(shop, target_url)
    await scraper.browser.close()


def send_home_depo_alert(workshop: dict, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    title = workshop.get("title")
    start = workshop.get("start").strip()
    msg = f"*<{link}|{title}>* on *{start}* is open for registration: {link}"

    # get last alert date
    alert_date = get_last_alert_date("home_depo")
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date("home_depo", current_date)
    else:
        log.info("No alerts were needed.")


async def run2(proxy: str = None, port: int = None) -> None:
    from playwright.async_api import async_playwright

    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    async with async_playwright() as playwright:
        context = await playwright.request.new_context()
        response = await context.get(target_url)
        content = await response.json()
        log.info(f"{json.dumps(content['workshopEventWsDTO'], indent=4)}")
        for event in content['workshopEventWsDTO']:
            event_type = event.get("workshopType", "")
            seats_left = event.get("remainingSeats")
            status = event.get("workshopStatus")
            details = event.get("eventType")
            title = details.get("name")
            start = event.get("eventDate")
            if event_type == "KID" and status == "ACTIVE":
                if seats_left > 0:
                    # get last alert date
                    alert_date = get_last_alert_date("home_depo")
                    log.info(f"Previous alert was sent on {alert_date}")
                    current_date = datetime.now().date()
                    if not alert_date or alert_date < current_date:
                        log.info("Sending new alert...")
                        link = "https://www.homedepot.ca/workshops?store=7265"
                        msg = f"*<{link}|{title}>* starts on *{start}* is open for registration: {link}"
                        send_slack_message(msg)
                        update_last_alert_date("home_depo", current_date)
                    else:
                        log.info("No alerts were needed.")
                else:
                    log.info(f"{title} starts on {start} is fully registed")
            else:
                log.info(f"{title} is not active or for kids")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run2())
