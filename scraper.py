import asyncio
import os
import sys
from pprint import pprint

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

nest_asyncio.apply()

PROXY_API_KEY = "PROXY_API_KEY"
PROXY_USER = "PROXY_USER"


def get_proxy_auth() -> dict:
    """
    Check if the proxy authentication keys are set
    :return:
    """
    if not os.environ.get(PROXY_API_KEY):
        sys.exit(f"{PROXY_API_KEY} not set")
    if not os.environ.get(PROXY_USER):
        sys.exit(f"{PROXY_USER} not set")
    return {
        "PROXY_API_KEY": os.environ.get(PROXY_API_KEY),
        "PROXY_USER": os.environ.get(PROXY_USER)
    }


class Scraper:
    def __init__(self, launch_options: dict) -> None:
        self.page = None
        self.browser = None
        self.options = launch_options.get("options")
        self.viewPort = launch_options.get("viewPort")
        self.proxy_auth = get_proxy_auth()

    async def goto(self, url: str) -> None:
        self.browser = await launch(options=self.options)
        self.page = await self.browser.newPage()
        # add proxy auth
        # await self.page.authenticate(
        #     {
        #         'username': self.proxy_auth.get(PROXY_USER),
        #         'password': self.proxy_auth.get(PROXY_API_KEY)
        #     }
        # )
        await self.page.setUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.5 Safari/605.1.15",
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.setViewport(
            self.viewPort) if self.viewPort is not None else print(
            "[i] using default viewport")
        await self.page.goto(url)

        # wait for specific time
        await self.page.waitFor(60000)
        # wait for element to appear
        # await self.page.waitForSelector('h1', {'visible': True})

        # click a button
        # link = await self.page.querySelector("h1")
        # await link.click()

        # Scroll To Bottom
        await self.page.evaluate(
            """{window.scrollBy(0, document.body.scrollHeight);}"""
        )

        # take a screenshot
        await self.page.screenshot({'path': 'screenshot.png'})

    async def get_full_content(self) -> str:
        content = await self.page.content()
        return content

    async def type_value(self, selector: str, value: str) -> None:
        """
        Write value to input field
        :param selector:
        :param value:
        :return:
        """
        element = await self.page.querySelector(selector)
        await element.type(value)

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

    async def extract_one(self, selector:str, attr: str) -> str:
        """
        Locate a single element using querySelector
        :param selector:
        :param attr:
        :return:
        """
        element = await self.page.querySelector(selector)
        text = await element.getProperty(attr)
        return await text.jsonValue()


async def run():
    # define launch option
    launch_options = {
        "options": {
            "headless": False,
            "autoClose": False,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-notifications",
                "--start-maximized",
                "--proxy-server=103.117.192.14:8080"
                # "--proxy-server=proxy.scrapeops.io:5353"
                # set a proxy server
                # have to add
                # await page.authenticate({'username': 'user', 'password': 'password'})
                # after await browser.newPage()
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
    # target_url = "https://ca.hotels.com/ho237271/simba-run-condos-2bed-2bath-vail-united-states-of-america/"
    target_url = "https://quotes.toscrape.com/"
    # target_url = f"https://proxy.scrapeops.io/v1/?api_key={scraper.proxy_auth.get(PROXY_API_KEY)}&url=" + target_url
    pprint(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    # Type "this is me" inside the input box
    # pprint("Type 'this is me' inside the input box")
    # await scraper.type_value("#fish", "this is me")

    # Scrape the entire page
    # pprint("Scrape entire page")
    # content = await scraper.get_full_content()
    # print(content)

    # Scrape one single element
    pprint("Scrape one single element")
    elem = await scraper.extract_one("h1", "textContent")
    print(elem)

    # Scrape multiple elements
    pprint("Scrape multiple elements")
    elems = await scraper.extract_many("li[role=listitem", "textContent")
    print(elems)

    # Execute javascript
    # content = await page.evaluate(
    # 'document.body.textContent', force_expr=True)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
