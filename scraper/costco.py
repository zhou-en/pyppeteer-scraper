import asyncio
import os
import platform
import sys
import json
from time import sleep

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
SCRAPER = "costco"
log = my_logger.CustomLogger(SCRAPER, verbose=True, log_dir="logs")


nest_asyncio.apply()


# class Scraper:
#     def __init__(self, launch_options: dict) -> None:
#         self.page = None
#         self.browser = None
#         self.options = launch_options.get("options")
#         self.viewPort = launch_options.get("viewPort")

#     async def goto(self, url: str) -> None:
#         self.browser = await launch(options=self.options)
#         self.page = await self.browser.newPage()
#         await self.page.setUserAgent(
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
#         )
#         # make scraper stealth
#         await stealth(self.page)
#         await self.page.goto(url, {"waitUntil": "load", "timeout": 600000})

#         # # wait for specific time to bypass store selection
#         # await self.page.waitFor(3000)
#         # wait for zip input box
#         selector = 'input[id="eddZipCodeField"]'
#         await self.page.waitForSelector(selector, {"visible": True, "timeout": 600000})

#         # close location select modal
#         close_btn = await self.page.querySelector("button[class*=acl-reset-button]")
#         if close_btn:
#             await close_btn.click()
#             await self.page.waitFor(5000)

#         # click kid diy tab button
#         link = await self.page.querySelector(selector)
#         await link.click()
#         await self.page.waitFor(5000)

#     async def extract_many(self, selector: str, attr: str) -> list:
#         """
#         Select and return a list of elements using queryAll
#         :param selector:
#         :param attr:
#         :return:
#         """
#         result = []
#         elements = await self.page.querySelectorAll(selector)
#         for element in elements:
#             text = await element.getProperty(attr)
#             result.append(await text.jsonValue())
#         return result

#     async def extract_one(self, selector: str, attr: str) -> str:
#         """
#         Locate a single element using querySelector
#         :param selector:
#         :param attr:
#         :return:
#         """
#         element = await self.page.querySelector(selector)
#         text = await element.getProperty(attr)
#         return await text.jsonValue()


# async def run(proxy: str = None, port: int = None) -> None:
#     # define launch option
#     launch_options = {
#         "options": {
#             "headless": True,
#             # "timeout": 50000,
#             "autoClose": False,
#             "args": [
#                 "--no-sandbox",
#                 "--disable-notifications",
#                 "--start-maximized",
#             ],
#             "ignoreDefaultArgs": ["--disable-extensions", "--enable-automation"],
#             "defaultViewport": {"width": 1920, "height": 1080},
#             "executablePath": BROWSER_PATH,
#         },
#     }

#     # Initialize the new scraper
#     scraper = Scraper(launch_options)

#     # Navigate to the target
#     target_url = (
#         "https://www.costco.ca/aiden-%2526-ivy-6-piece-fabric-sectional%2c-grey.product.4000207338.html?langId=-24&province=SK&sh=true&nf=true"
#     )

#     log.info(f"Navigate to: {target_url}")
#     await scraper.goto(target_url)

#     log.info(f"Start scraping {SCRAPER}...")

#     ws_elements = await scraper.page.querySelectorAll("localized-tabs-content > div")
#     log.info(f"{len(ws_elements)} events found")
#     for workshop in ws_elements:
#         title_elem = await workshop.querySelector("h3")
#         title = await title_elem.getProperty("textContent")
#         title_str = await title.jsonValue()
#         status_elem = await workshop.querySelector("button")
#         status = await status_elem.getProperty("textContent")
#         status_str = await status.jsonValue()
#         start_elem = await workshop.querySelector("p")
#         start = await start_elem.getProperty("textContent")
#         start_str = await start.jsonValue()
#         log.info(f"Found event: {title_str}, status: {status_str}")
#         if "full" in status_str.lower() or "closed" in status_str.lower():
#             log.info("Event is not open for registration!")
#             continue
#         shop = {"title": title_str, "start": start_str, "status": status_str}
#         if "register" in status_str.lower():
#             log.info(f"{title_str} is open for registration: {status_str}")
#             send_costco_alert(shop, target_url)
#     await scraper.browser.close()


def send_costco_alert(product: str, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    msg = f"*<{link}|{product}>* is available now!"

    # get last alert date
    alert_date = get_last_alert_date(f"{SCRAPER}")
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date(f"{SCRAPER}", current_date)
    else:
        log.info("No alerts were needed.")


async def run2(proxy: str = None, port: int = None) -> None:
    from playwright.async_api import async_playwright

    target_url = (
        "https://www.costco.ca/aiden-%2526-ivy-6-piece-fabric-sectional%2c-grey.product.4000207338.html?langId=-24&province=SK&sh=true&nf=true"
    )
    product = "Aiden & Ivy 6-piece Fabric Sectional, Grey"

    async with async_playwright() as playwright:
        # Launch the Chromium browser in non-headless mode (visible UI) to see
        # the browser in action.
        browser = await playwright.chromium.launch(headless=True)

        # Open a new browser page.
        page = await browser.new_page(viewport={'width': 1600, 'height': 900})

        # Short sleep to be able to see the browser in action.
        await asyncio.sleep(1)

        # Navigate to the specified URL.
        await page.goto(target_url)

        sleep(5)
        await page.click('id=onetrust-accept-btn-handler')
        sleep(1)

        change_zip_selector = "#edd-outofstock > span + a"
        await page.click(change_zip_selector)
        sleep(1)

        input_selector = "#eddZipCodeField"
        zip = "S7T 0J6"
        await page.fill(input_selector, zip)

        await page.click("#edd-check-button")
        sleep(3)

        # Get the value of the "value" attribute for the input field
        value = await page.get_attribute("#add-to-cart-btn", "value")

        # Check if the value is "Out of Stock"
        if value == "Out of Stock":
            log.info(f"{product} is still out of stock")
        else:
            send_costco_alert(product, target_url)

        await browser.close()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run2())
