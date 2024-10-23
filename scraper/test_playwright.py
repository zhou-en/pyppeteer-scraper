import asyncio
import nest_asyncio
from time import sleep
nest_asyncio.apply()

from playwright.async_api import async_playwright

url = "https://www.costco.ca/aiden-%2526-ivy-6-piece-fabric-sectional%2c-grey.product.4000207338.html?langId=-24&province=SK&sh=true&nf=true"
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        sleep(5)
        await browser.close()
        print(page.title)

asyncio.run(main())
