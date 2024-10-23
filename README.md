# pyppeteer-scraper

Web scraper using pyppeteer

## Diagram
![alt text](image.png)

## References

- https://github.com/pyppeteer/pyppeteer
- https://www.webscrapingapi.com/pyppeteer?utm_source=pocket_saves
- https://blog.apify.com/python-playwright/

## Environment Variables

### Proxy (optional)
- `API_KEY`: proxy server API key
- `API_URL`: proxy server URL, no trailing slash
  - https://proxy.scrapeops.io/v1
  - https://api.webscrapingapi.com/v1
- `API_USER`: username for API authentication
  - WebScrapingAPI doesn't need it

### Slack

- `SLACK_API_TOKEN`:
- `CHANNEL_ID`:
  - Right-click on the channel name and select `View channel details`, ID is at
    the bottom of the window
- `BROWSER_PATH`: path to Chromium browser executable
  - `/usr/bin/chromium-browser` on Raspberry Pi
  - `/Applications/Chromium.app/Contents/MacOS/Chromium` on Macbook
  - `/usr/bin/chromium` on Linux Mint

## Deployment on Raspberry Pi

### Use Playwright as scraper
```sh
pip install playwright
playwright install
```

### OSError: [Errno 8] Exec format error: '/home/pi/.local/share/pyppeteer/local-chromium/588429/chrome-linux/chrome
If a Chromium browser is installed already:
- `cd /home/pi/.local/share/pyppeteer/local-chromium/588429/chrome-linux`
- remove anything if there is any
- `ln -s /usr/bin/chromium/ chrome`

If no Chromium is not installed, install it with the follow command and repeat above step:
`sudo apt install chromium -y`

## Cron Jobs

### Raspberry Pi
```shell
# run every hour between 7 and 22 o'clock
0 7-22 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log

# run every hour between 7 - 22 o'clock
0 7-22 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/library_event.py > /tmp/stdout.log 2> /tmp/stderr.log

# run at 9am everyday
0 9 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/stonebridge_event.py > /tmp/stdout.log 2> /tmp/stderr.log


# clean up logs once a week At 00:00 on Sunday
0 0 * * 0 cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python logger/cleanup.py > /tmp/stdout.log 2> /tmp/stderr.log
```

### Macbook
```shell
# run every hour between 9:00 and 16:00 from Monday to Friday
0 9-16 * * 1-5 cd /Users/enzhou/Projects/pyppeteer-scraper && /Users/enzhou/anaconda3/envs/pyppeteer/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log
```

### Costco Scrpaer

- Install `chromedriver` on raspberry pi: `sudo apt-get install chromium-chromedriver`
  - path: `/usr/bin/chromedriver`
  - On MacOS: `brew install chromedriver`
    - path: `/opt/homebrew/bin/chromedriver`
