# pyppeteer-scraper

Web scraper using pyppeteer

## References

- https://github.com/pyppeteer/pyppeteer
- https://www.webscrapingapi.com/pyppeteer?utm_source=pocket_saves

## Environment Variables

### Proxy
- `API_KEY`: proxy server API key
- `API_URL`: proxy server URL, no trailing slash
  - https://proxy.scrapeops.io/v1
  - https://api.webscrapingapi.com/v1
- `API_USER`: username for API authentication
  - WebScrapingAPI doesn't need it

### Slack
- `SLACK_API_TOKEN`:  
- `CHANNEL_ID`: 

## Deployment on Raspberry Pi

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
0 7-22 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py

# run every hour between 7 - 22 o'clock
0 7-22 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/library_event.py

# run at 9am everyday
0 9 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/stonebridge_event.py


# clean up logs once a week At 00:00 on Sunday
0 0 * * 0 cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python logger/cleanup.py
```

### Macbook
```shell
# run every hour between 9:00 and 16:00 from Monday to Friday
0 9-16 * * 1-5 cd /Users/enzhou/Projects/pyppeteer-scraper && /Users/enzhou/anaconda3/envs/pyppeteer/bin/python scraper/home_depo.py
```
