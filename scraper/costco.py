import json
import os
import sys
from time import sleep

import psycopg2
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

load_dotenv()

from service.alert import send_slack_message

SCRAPER_NAME = "costco"
log = my_logger.CustomLogger(SCRAPER_NAME, verbose=True, log_dir="logs")

PRODUCTS_PATH = os.path.join(parent, "config", "costco_products.json")
with open(PRODUCTS_PATH) as f:
    PRODUCTS = json.load(f)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

session = curl_requests.Session()

# Warm up session on homepage so Akamai sets its cookies
log.info("Warming up session on costco.ca...")
resp = session.get("https://www.costco.ca", impersonate="chrome110", headers=HEADERS)
log.info(f"Homepage status: {resp.status_code}")
sleep(2)


def _db_conn():
    return psycopg2.connect(os.environ["POSTGRES_URL"])


def _ensure_state_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS costco_state (
            product_id       TEXT PRIMARY KEY,
            product_name     TEXT,
            last_known_price NUMERIC,
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def _get_last_price(cur, product_id):
    cur.execute(
        "SELECT last_known_price FROM costco_state WHERE product_id = %s",
        (product_id,),
    )
    row = cur.fetchone()
    return float(row[0]) if row else None


def _save_price(cur, product_id, product_name, price):
    cur.execute(
        """
        INSERT INTO costco_state (product_id, product_name, last_known_price, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (product_id) DO UPDATE
            SET last_known_price = EXCLUDED.last_known_price,
                updated_at       = NOW()
        """,
        (product_id, product_name, price),
    )


def scrape_product(product):
    url = product["url"]
    name = product["name"]
    product_id = product["id"]

    log.info(f"Scraping: {name}")
    product_headers = {**HEADERS, "Sec-Fetch-Site": "same-origin", "Referer": "https://www.costco.ca/"}
    resp = session.get(url, impersonate="chrome110", headers=product_headers)
    log.info(f"Product page status: {resp.status_code}")

    if resp.status_code != 200:
        log.error(f"Unexpected status {resp.status_code}:\n{resp.text[:500]}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    price_el = soup.select_one("#pull-right-price .value")

    if not price_el:
        log.error("Price element not found in page HTML")
        log.info(f"Page snippet:\n{resp.text[:2000]}")
        return

    price_text = price_el.get_text(strip=True).replace(",", "")
    current_price = float(price_text)
    log.info(f"Current price: ${current_price:.2f}")

    conn = _db_conn()
    cur = conn.cursor()
    try:
        _ensure_state_table(cur)
        last_price = _get_last_price(cur, product_id)

        if last_price is None:
            log.info(f"First run — recording price ${current_price:.2f}")
        elif current_price < last_price:
            drop = last_price - current_price
            log.info(f"Price dropped! ${last_price:.2f} → ${current_price:.2f} (save ${drop:.2f})")
            msg = (
                f"*<{url}|{name}>* price dropped!\n"
                f"*${last_price:.2f}* → *${current_price:.2f}* (save *${drop:.2f}*)"
            )
            send_slack_message(msg)
        else:
            log.info(f"No drop. Current ${current_price:.2f}, last ${last_price:.2f}")

        _save_price(cur, product_id, name, current_price)
        conn.commit()
    finally:
        cur.close()
        conn.close()


for product in PRODUCTS:
    scrape_product(product)
