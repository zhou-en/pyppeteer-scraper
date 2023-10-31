import asyncio
import os
from pprint import pprint

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

from service.alert import send_slack_alert

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
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.5 "
            "Safari/605.1.15",
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.goto(url)

        # wait for specific time
        # await self.page.waitFor(60000)
        # wait for element to appear
        await self.page.waitForSelector('span[data-title*="Kids Workshops"]', {'visible': True})

        # click a button
        link = await self.page.querySelector('span[data-title*="Kids Workshops"]')
        await link.click()

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
            "autoClose": False,
            "args": [
                "--no-sandbox",
                "--disable-notifications",
                "--start-maximized",
            ],
            "ignoreDefaultArgs": ["--disable-extensions", "--enable-automation"]
        },
        "viewPort": {
            "width": 1600,
            "height": 900
        }
    }

    # Initialize the new scraper
    scraper = Scraper(launch_options)

    # Navigate to the target
    target_url = "https://www.homedepot.ca/workshops?store=7265"

    pprint(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    pprint("Scrape Kids Workshop")
    workshop_titles = await scraper.extract_many("localized-tabs-content h3.hdca-text-title", "textContent")
    reg_status = await scraper.extract_many("localized-tabs-content button span.acl-button__label", "textContent")
    if 'Register' in reg_status:
        send_home_depo_alert(workshop_titles, reg_status, target_url)
    await scraper.browser.close()


def send_home_depo_alert(titles, statuses, link):
    """
    Creates a list of workshops and its status
    :param link: registration link
    :param titles: a list of space separated names
    :param statuses: a list of registration statuses
    :return:
    """
    for i, status in enumerate(statuses):
        if status == "Register":
            title = titles[i]
            msg = f"\"{title}\" is open for registration: {link}"
            send_slack_alert(msg)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())