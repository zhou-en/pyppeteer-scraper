import asyncio
import json
import os
import platform
import sys

import requests
from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import my_logger

load_dotenv()

BROWSER_PATH = os.environ.get("BROWSER_PATH")
if platform.system() != "Darwin":
    if (
        "/home/pi/Projects/pyppeteer-scraper" not in sys.path
        and "/home/pi" in ",".join(sys.path)
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

log = my_logger.CustomLogger("home_depo", verbose=True, log_dir="logs")


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
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        )
        # make scraper stealth
        await stealth(self.page)
        await self.page.goto(url, {"waitUntil": "load", "timeout": 600000})

        # # wait for specific time to bypass store selection
        await self.page.waitFor(3000)
        # wait for element to appear
        selector = 'span[data-title*="Kids Workshops"]'
        await self.page.waitForSelector(selector, {"visible": True, "timeout": 600000})

        # close location select modal
        close_btn = await self.page.querySelector("button[class*=acl-reset-button]")
        if close_btn:
            await close_btn.click()
            await self.page.waitFor(5000)

        # click kid diy tab button
        link = await self.page.querySelector(selector)
        await link.click()
        await self.page.waitFor(5000)

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
            # "timeout": 50000,
            "autoClose": False,
            "args": [
                "--no-sandbox",
                "--disable-notifications",
                "--start-maximized",
            ],
            "ignoreDefaultArgs": ["--disable-extensions", "--enable-automation"],
            "defaultViewport": {"width": 1920, "height": 1080},
            "executablePath": BROWSER_PATH,
        },
    }

    # Initialize the new scraper
    scraper = Scraper(launch_options)

    # Navigate to the target
    # target_url = "https://www.homedepot.ca/workshops?store=7265"
    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    log.info(f"Navigate to: {target_url}")
    await scraper.goto(target_url)

    log.info("Start scraping Kids Workshop...")

    ws_elements = await scraper.page.querySelectorAll("localized-tabs-content > div")
    log.info(f"{len(ws_elements)} events found")
    for workshop in ws_elements:
        title_elem = await workshop.querySelector("h3")
        title = await title_elem.getProperty("textContent")
        title_str = await title.jsonValue()
        status_elem = await workshop.querySelector("button")
        status = await status_elem.getProperty("textContent")
        status_str = await status.jsonValue()
        start_elem = await workshop.querySelector("p")
        start = await start_elem.getProperty("textContent")
        start_str = await start.jsonValue()
        log.info(f"Found event: {title_str}, status: {status_str}")
        if "full" in status_str.lower() or "closed" in status_str.lower():
            log.info("Event is not open for registration!")
            continue
        shop = {"title": title_str, "start": start_str, "status": status_str}
        if "register" in status_str.lower():
            log.info(f"{title_str} is open for registration: {status_str}")
            send_home_depo_alert(shop, target_url)
    await scraper.browser.close()


def send_home_depo_alert(workshop: dict, link):
    """
    Creates a list of workshops and its status
    :param workshop: details of workshop, i.e. title, start, status
    :return:
    """

    title = workshop.get("title")
    start = workshop.get("start").strip()
    msg = f"*<{link}|{title}>* on *{start}* is open for registration: {link}"

    # get last alert date
    alert_date = get_last_alert_date("home_depo")
    log.info(f"Previous alert was sent on {alert_date}")
    current_date = datetime.now().date()
    if not alert_date or alert_date < current_date:
        log.info("Sending new alert...")
        send_slack_message(msg)
        update_last_alert_date("home_depo", current_date)
    else:
        log.info("No alerts were needed.")


def register_home_depot_workshop(
    event_code,
    workshop_event_id,
    first_name="En",
    last_name="Zhou",
    email="zhouen.nathan@gmail.com",
    store_id="7265",
    participant_count=2,
    dry_run=False,
):
    """
    Register for a Home Depot workshop
    Args:
        event_code: The specific event code (e.g., "KWBE0001")
        workshop_event_id: The workshop event ID (e.g., "WS00029")
        first_name: First name for registration
        last_name: Last name for registration
        email: Email for registration
        store_id: Store ID for the workshop location
        participant_count: Number of participants
        dry_run: If True, only log the request without sending it
    Returns:
        tuple: (success, response_text)
    """
    from service.alert import send_api_error_alert

    log.info(
        f"Attempting to register for workshop with event code: {event_code}, workshop event ID: {workshop_event_id}"
    )

    url = f"https://www.homedepot.ca/api/workshopsvc/v1/workshops/{workshop_event_id}/events/{event_code}/signups?lang=en"
    log.info(f"Registration URL: {url}")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
    }
    log.info(f"Request headers: {headers}")

    payload = {
        "customer": {"firstName": first_name, "lastName": last_name, "email": email},
        "workshopEventCode": event_code,
        "store": store_id,
        "participantCount": participant_count,
        "guestParticipants": [],
        "lang": "en",
    }
    log.info(f"Request payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        log.info("DRY RUN - Request not sent")
        return True, json.dumps(
            {
                "dry_run": True,
                "would_send": {"url": url, "headers": headers, "payload": payload},
            }
        )

    try:
        log.info("Sending registration request...")
        response = requests.post(url, headers=headers, json=payload)

        log.info(f"Response status code: {response.status_code}")
        log.info(f"Response headers: {dict(response.headers)}")

        try:
            response_json = response.json()
            log.info(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError as e:
            log.warning(f"Response is not JSON: {response.text[:500]}")
            send_api_error_alert(
                "Home Depot Registration",
                "JSON parsing error in registration response",
                f"Event code: {event_code}\nError: {str(e)}\nResponse: {response.text[:500]}",
            )

        if response.ok:
            log.info("Registration request was successful")
            send_api_error_alert(
                "Home Depot Registration",
                f"✅ Registration successful for workshop {event_code}",
                f"Name: {first_name} {last_name}\nEmail: {email}\nStore: {store_id}\nParticipants: {participant_count}",
            )
            return True, response.text
        else:
            error_msg = f"Registration failed with status code {response.status_code}"
            log.error(error_msg)
            log.error(f"Error response: {response.text[:500]}")
            send_api_error_alert(
                "Home Depot Registration",
                f"❌ Registration failed for workshop {event_code}",
                f"Status: {response.status_code}\nName: {first_name} {last_name}\nResponse: {response.text[:500]}",
            )
            return False, response.text
    except requests.exceptions.RequestException as e:
        error_msg = f"Request exception occurred: {str(e)}"
        log.error(error_msg)
        send_api_error_alert(
            "Home Depot Registration",
            f"❌ Registration request error for workshop {event_code}",
            f"Error: {str(e)}\nURL: {url}",
        )
        return False, str(e)
    except Exception as e:
        error_msg = f"Unexpected exception during registration: {str(e)}"
        log.error(error_msg, exc_info=True)
        send_api_error_alert(
            "Home Depot Registration",
            f"❌ Unexpected error during registration for workshop {event_code}",
            f"Error: {str(e)}",
        )
        return False, str(e)


def should_register_workshop(workshop_id, start_time, attendee_limit, remaining_seats):
    """
    Determine if we should register for this workshop.

    Args:
        workshop_id: The workshop ID (e.g., "KWHC0002", "KWBE0001")
        start_time: The start time string (e.g., "2025-10-11T08:30:00-0400")
        attendee_limit: Total number of seats available
        remaining_seats: Number of seats remaining

    Returns:
        tuple: (should_register: bool, reason: str)
    """
    # Check if workshop ID starts with "KW" (Kids Workshop)
    if not workshop_id.startswith("KW"):
        return False, f"Workshop ID '{workshop_id}' does not start with 'KW'"

    # Check if start time is 8:30
    if "08:30" not in start_time:
        return False, f"Start time is not 8:30 AM"

    # Don't be the first to register - wait until at least 1 person has registered
    seats_taken = attendee_limit - remaining_seats
    if seats_taken < 1:
        return (
            False,
            f"No one has registered yet (seats taken: {seats_taken}). Waiting for someone else to register first.",
        )

    # All conditions met
    return (
        True,
        f"Workshop matches criteria: ID starts with 'KW', starts at 8:30 AM, and {seats_taken} person(s) already registered",
    )


async def run2(proxy: str = None, port: int = None) -> None:
    from playwright.async_api import async_playwright

    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    async with async_playwright() as playwright:
        context = await playwright.request.new_context()
        try:
            response = await context.get(target_url)

            # First check if the response is valid
            status = response.status
            log.info(f"Response status code: {status}")

            # Check for non-successful status codes
            if status != 200:
                error_msg = f"Home Depot API returned non-200 status code: {status}"
                log.error(error_msg)
                from service.alert import send_api_error_alert

                send_api_error_alert(
                    "Home Depot API",
                    error_msg,
                    f"URL: {target_url}\nStatus Code: {status}",
                )
                return

            # Log response headers and text content for debugging
            headers = response.headers
            log.info(f"Response headers: {headers}")

            text_content = await response.text()
            log.info(f"Response content preview: {text_content[:200]}")

            # Only try to parse as JSON if we have content
            if text_content.strip():
                try:
                    content = await response.json()

                    # Check if expected key exists
                    if "workshopEventWsDTO" not in content:
                        error_msg = "Home Depot API response missing expected 'workshopEventWsDTO' key"
                        log.error(error_msg)
                        from service.alert import send_api_error_alert

                        send_api_error_alert(
                            "Home Depot API",
                            error_msg,
                            f"Response Keys: {list(content.keys())}",
                        )
                        return

                    log.info(f"{json.dumps(content['workshopEventWsDTO'], indent=4)}")

                    if not content.get("workshopEventWsDTO"):
                        log.info("No workshop events found")
                        return

                    for event in content["workshopEventWsDTO"]:
                        workshop_id = event.get("workshopId", "")
                        event_type = event.get("workshopType", "")
                        details = event.get("eventType", {})
                        event_code = details.get(
                            "workshopEventId", ""
                        )  # FIX: get from eventType.workshopEventId
                        seats_left = event.get("remainingSeats", 0)
                        attendee_limit = event.get("attendeeLimit", 0)
                        status = event.get("workshopStatus", "")
                        title = details.get("name", "Unknown workshop")
                        event_date = event.get("eventDate", "")
                        start_time_str = event.get("startTime", "")
                        start_datetime = start_time_str
                        if start_time_str:
                            try:
                                # Handle ISO format with different timezone formats
                                # For formats like 2025-08-09T08:30:00-0400
                                if "-" in start_time_str and len(start_time_str) > 20:
                                    # Convert -0400 format to -04:00 which fromisoformat can handle
                                    offset_idx = start_time_str.rfind("-")
                                    if (
                                        offset_idx > 10
                                    ):  # Make sure we're looking at timezone, not date
                                        offset = start_time_str[offset_idx:]
                                        if len(offset) == 5:  # -0400 format
                                            new_offset = f"{offset[:3]}:{offset[3:]}"
                                            start_time_str = (
                                                start_time_str[:offset_idx] + new_offset
                                            )
                                # For Z format like 2023-12-31T14:00:00Z
                                start_time_str = start_time_str.replace("Z", "+00:00")
                                start_datetime = datetime.fromisoformat(start_time_str)
                            except ValueError as e:
                                log.warning(
                                    f"Could not parse date '{start_time_str}': {str(e)}"
                                )
                                # Continue with the original string if parsing fails
                                pass

                        log.info(
                            f"Found workshop: {title}, code: {event_code}, seats left: {seats_left}, status: {status}"
                        )

                        if seats_left == 0:
                            log.info(
                                f"{title} starts on {start_datetime} is fully registered"
                            )
                            continue
                        if event_type != "KID":
                            log.info(f"{title} is not a kid workshop, skipping...")
                            continue
                        if status != "ACTIVE":
                            log.info(f"{title} is not active, skipping...")
                            continue

                        # get last alert date
                        alert_date = get_last_alert_date("home_depo")
                        log.info(f"Previous alert was sent on {alert_date}")
                        current_date = datetime.now().date()

                        if alert_date and alert_date >= current_date:
                            log.info("No new alert is needed.")
                            continue

                        log.info("Sending new alert...")

                        # General workshop page link
                        workshop_page_link = (
                            "https://www.homedepot.ca/workshops?store=7265"
                        )

                        # Build a direct registration link if possible
                        registration_link = (
                            f"https://www.homedepot.ca/workshops?storeId=7265"
                        )

                        # Send standard alert for continuity
                        msg = f"*<{workshop_page_link}|{title}>* starts on *{start_datetime}* is open for registration: {workshop_page_link}"
                        send_slack_message(msg)

                        # Also send an urgent, high-visibility alert for time-sensitive workshops
                        from service.alert import send_urgent_workshop_alert

                        # Format date in a more readable way if possible
                        formatted_date = start_datetime
                        if isinstance(start_datetime, datetime):
                            formatted_date = start_datetime.strftime(
                                "%A, %B %d, %Y at %I:%M %p"
                            )

                        # Create workshop details for the urgent alert
                        workshop_details = {
                            "title": title,
                            "date": formatted_date,
                            "event_code": event_code,
                            "seats_left": seats_left,
                        }

                        # Send the urgent alert with direct registration link
                        send_urgent_workshop_alert(workshop_details, registration_link)

                        # Update last alert date
                        update_last_alert_date("home_depo", current_date)

                        # Check for specific workshops to register automatically
                        # Use the original start time string from API for the check
                        start_time_for_check = event.get("startTime", "")
                        should_register, reason = should_register_workshop(
                            workshop_id,
                            start_time_for_check,
                            attendee_limit,
                            seats_left,
                        )

                        if should_register:
                            registration_msg = (
                                f"🎯 Auto-registering for workshop:\n"
                                f"• Event Code: *{event_code}*\n"
                                f"• Workshop ID: *{workshop_id}*\n"
                                f"• Title: *{title}*\n"
                                f"• Date: *{formatted_date}*\n"
                                f"• Seats Left: *{seats_left}*\n"
                                f"• Reason: {reason}"
                            )
                            log.info(registration_msg)
                            send_slack_message(registration_msg)

                            log.info(
                                f"Registering workshop - Event Code: {event_code}, Workshop Event ID: {event_code}..."
                            )
                            success, response = register_home_depot_workshop(
                                workshop_id, event_code
                            )
                            if success:
                                success_msg = (
                                    f"✅ Successfully registered:\n"
                                    f"• Event: *{title}*\n"
                                    f"• Workshop ID: *{workshop_id}*\n"
                                    f"• Workshop Event ID: *{event_code}*\n"
                                    f"• Date: *{formatted_date}*\n"
                                    f"• Link: {registration_link}"
                                )
                                log.info(success_msg)
                                send_slack_message(success_msg)
                            else:
                                error_msg = (
                                    f"❌ Registration failed for:\n"
                                    f"• Event: *{title}*\n"
                                    f"• Workshop ID: *{workshop_id}*\n"
                                    f"• Workshop Event ID: *{event_code}*\n"
                                    f"• Error: {response}"
                                )
                                log.error(error_msg)
                                send_slack_message(error_msg)
                        else:
                            # Send notification that registration was skipped with reason
                            skip_msg = (
                                f"⏭️ Skipping auto-registration:\n"
                                f"• Event: *{title}*\n"
                                f"• Workshop ID: *{workshop_id}*\n"
                                f"• Date: *{formatted_date}*\n"
                                f"• Seats Left: *{seats_left}*\n"
                                f"• Reason: {reason}"
                            )
                            log.info(skip_msg)
                            send_slack_message(skip_msg)
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to decode JSON response: {e}"
                    log.error(error_msg)
                    log.error(f"Response content was: {text_content[:500]}")
                    from service.alert import send_api_error_alert

                    send_api_error_alert(
                        "Home Depot API",
                        "JSON parsing error",
                        f"Error: {str(e)}\nFirst 500 chars of response: {text_content[:500]}",
                    )
                    return
            else:
                error_msg = "Received empty response from Home Depot API"
                log.error(error_msg)
                from service.alert import send_api_error_alert

                send_api_error_alert("Home Depot API", error_msg, f"URL: {target_url}")
                return
        except Exception as e:
            error_msg = f"Unexpected error accessing Home Depot API: {str(e)}"
            log.error(error_msg, exc_info=True)
            from service.alert import send_api_error_alert

            send_api_error_alert(
                "Home Depot API",
                "Unexpected error",
                f"Error: {str(e)}\nURL: {target_url}",
            )
            return


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run2())
