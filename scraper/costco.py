import json
import os
import platform
import sys
from datetime import datetime
from time import sleep

import psycopg2
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

options = Options()
options.add_argument("--headless")
options.add_argument("--window-size=1920,1200")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/89.0.4389.82 Safari/537.36"
)

BROWSER_BINARY = os.environ.get("BROWSER_PATH", "")
if platform.system() == "Darwin":
    pass  # auto-detect on macOS
elif BROWSER_BINARY:
    options.binary_location = BROWSER_BINARY
else:
    options.binary_location = "/usr/bin/chromium-browser"

DRIVER_PATH_ENV = os.environ.get("CHROMEDRIVER_PATH", "")
if DRIVER_PATH_ENV:
    driver = webdriver.Chrome(service=Service(DRIVER_PATH_ENV), options=options)
else:
    driver = webdriver.Chrome(options=options)  # Selenium Manager auto-downloads


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
    driver.get(url)

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
    except Exception:
        pass  # cookie prompt absent

    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#out-of-stock-zip-code + a"))
        ).click()

        zip_field = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "eddZipCodeField"))
        )
        zip_field.clear()
        zip_field.send_keys("S7T 0J6")

        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "edd-check-button"))
        ).click()
        sleep(2)
    except Exception as e:
        log.warning(f"Postal code flow skipped: {e}")

    try:
        price_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#pull-right-price .value"))
        )
        price_text = price_el.text.replace(",", "").strip()
        current_price = float(price_text)
        log.info(f"Current price: ${current_price:.2f}")
    except Exception as e:
        log.error(f"Could not extract price: {e}")
        return

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


try:
    for product in PRODUCTS:
        scrape_product(product)
finally:
    driver.quit()
