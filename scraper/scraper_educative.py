import asyncio
from typing import List

from pyppeteer import launch


async def get_article_titles(keywords: List[str]):
    # launch browser in headless mode
    browser = await launch(
        {"headless": False, "args": ["--start-maximized", "--no-sandbox"]})
    # create a new page
    page = await browser.newPage()
    # set page viewport to the largest size
    await page.setViewport({"width": 1600, "height": 900})
    # navigate to the page
    await page.goto("https://www.educative.io/edpresso")
    # locate the search box
    entry_box = await page.querySelector(
        "input[type=\"text\"]"
    )

    for keyword in keywords:
        print(
            "====================== {} ======================".format(keyword))
        # type keyword in search box
        await entry_box.type(keyword)
        # wait for search results to load
        await page.waitFor(4000)
        # extract the article titles
        topics = await page.querySelectorAll("h2")
        for topic in topics:
            title = await topic.getProperty("textContent")
            # print the article titles
            print(await title.jsonValue())

        # clear the input box
        for _ in range(len(keyword)):
            await page.keyboard.press("Backspace")


print("Starting...")
asyncio.get_event_loop().run_until_complete(
    get_article_titles(["python", "opensource", "opencv"])
)
print("Finished extracting articles titles")
