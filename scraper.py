import asyncio
from pprint import pprint

import nest_asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/93.0.4577.82 Safari/537.36"
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.setViewport(
            self.viewPort) if self.viewPort is not None else print(
            "[i] using default viewport")
        await self.page.goto(url)

        # wait for specific time
        await self.page.waitFor(500)
        # wait for element to appear
        await self.page.waitForSelector('h1', {'visible': True})

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
                # "--proxy-server=ip:port"  # set a proxy server
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
    url = "https://ca.hotels.com/ho237271/simba-run-condos-2bed-2bath-vail-united-states-of-america/"
    # url = "https://quotes.toscrape.com/"
    pprint(f"Navigate to: {url}")
    await scraper.goto(url)

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
