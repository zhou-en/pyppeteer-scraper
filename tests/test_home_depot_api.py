import asyncio
import json
import os
import sys

import requests

# Add parent directory to path to allow imports
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import my_logger
from playwright.async_api import async_playwright

# Initialize logger
log = my_logger.CustomLogger("test_home_depot", verbose=True, log_dir="../logs")


async def test_playwright_api_request():
    """
    Test the Home Depot API using Playwright
    """
    log.info("Testing Home Depot API with Playwright...")
    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    async with async_playwright() as playwright:
        context = await playwright.request.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0"
        )

        # Add additional headers if needed
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.homedepot.ca/workshops?store=7265",
        }

        log.info(f"Sending request to: {target_url}")
        log.info(f"With headers: {headers}")

        response = await context.get(target_url, headers=headers)

        # Log response details
        status = response.status
        log.info(f"Response status code: {status}")

        resp_headers = response.headers
        log.info(f"Response headers: {resp_headers}")

        text_content = await response.text()
        log.info(f"Response length: {len(text_content)} characters")
        log.info(f"Response content preview: {text_content[:200]}")

        # Try to parse as JSON
        if text_content.strip():
            try:
                content = json.loads(text_content)
                log.info("Successfully parsed JSON response")

                # Check if the expected key exists
                if "workshopEventWsDTO" in content:
                    log.info(
                        f"Found {len(content['workshopEventWsDTO'])} workshop events"
                    )
                    log.info(
                        f"First event: {json.dumps(content['workshopEventWsDTO'][0], indent=2)}"
                    )

                    # Return the first event code for registration test
                    for event in content["workshopEventWsDTO"]:
                        if (
                            event.get("workshopType") == "KID"
                            and event.get("remainingSeats", 0) > 0
                        ):
                            return event["eventType"]["workshopEventId"]
                else:
                    log.info(f"Response keys: {list(content.keys())}")
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON response: {e}")
                log.error(f"Response content was: {text_content[:500]}")
        else:
            log.error("Received empty response from server")

        return None


def test_requests_api():
    """
    Test the Home Depot API using the requests library
    """
    log.info("Testing Home Depot API with requests library...")
    target_url = (
        "https://www.homedepot.ca/api/workshopsvc/v1/workshops/all?storeId=7265&lang=en"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.homedepot.ca/workshops?store=7265",
    }

    log.info(f"Sending request to: {target_url}")
    log.info(f"With headers: {headers}")

    try:
        response = requests.get(target_url, headers=headers)

        log.info(f"Response status code: {response.status_code}")
        log.info(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            content_length = len(response.text)
            log.info(f"Response length: {content_length} characters")
            log.info(f"Response content preview: {response.text[:200]}")

            try:
                json_data = response.json()
                log.info("Successfully parsed JSON response")

                if "workshopEventWsDTO" in json_data:
                    log.info(
                        f"Found {len(json_data['workshopEventWsDTO'])} workshop events"
                    )
                    log.info(
                        f"First event: {json.dumps(json_data['workshopEventWsDTO'][0], indent=2)}"
                    )

                    # Return the first event code for registration test
                    for event in json_data["workshopEventWsDTO"]:
                        if (
                            event.get("workshopType") == "KID"
                            and event.get("remainingSeats", 0) > 0
                        ):
                            return event["eventType"]["workshopEventId"]
                else:
                    log.info(f"Response keys: {list(json_data.keys())}")
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON response: {e}")
                log.error(f"Response content was: {response.text[:500]}")
        else:
            log.error(f"Request failed with status code: {response.status_code}")
            log.error(f"Response content: {response.text[:500]}")
    except requests.exceptions.RequestException as e:
        log.error(f"Request exception: {str(e)}")

    return None


def test_registration_api(event_code=None, dry_run=True):
    """
    Test the Home Depot workshop registration API

    Args:
        event_code: The event code to register for. If None, will use a test code.
        dry_run: If True, will not actually submit the registration.
    """
    if not event_code:
        event_code = "TEST_EVENT_CODE"  # Default test code
        log.info(f"No event code provided, using test code: {event_code}")

    log.info(f"Testing Home Depot registration API for event code: {event_code}")

    # Registration endpoint
    url = f"https://www.homedepot.ca/api/workshopsvc/v1/workshops/WS00023/events/{event_code}/signups?lang=en"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.homedepot.ca/workshops?store=7265",
    }

    # Test registration data - replace with your test data
    payload = {
        "customer": {
            "firstName": "Test",
            "lastName": "User",
            "email": "test@example.com",
        },
        "workshopEventCode": event_code,
        "store": "7265",
        "participantCount": 1,
        "guestParticipants": [],
        "lang": "en",
    }

    log.info(f"Registration URL: {url}")
    log.info(f"Registration headers: {headers}")
    log.info(f"Registration payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        log.info("DRY RUN - Registration request not sent")
        return True, "Dry run completed"

    try:
        # Send the registration request
        response = requests.post(url, headers=headers, json=payload)

        log.info(f"Registration response status code: {response.status_code}")
        log.info(f"Registration response headers: {dict(response.headers)}")

        try:
            response_json = response.json()
            log.info(f"Registration response: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError:
            log.warning(f"Registration response is not JSON: {response.text[:500]}")

        if response.ok:
            log.info("Registration request was successful")
            return True, response.text
        else:
            log.error(f"Registration failed with status code {response.status_code}")
            log.error(f"Error response: {response.text[:500]}")
            return False, response.text
    except requests.exceptions.RequestException as e:
        log.error(f"Registration request exception occurred: {str(e)}")
        return False, str(e)


async def test_registration_api_playwright(event_code=None, dry_run=True):
    """
    Test the Home Depot workshop registration API using Playwright

    Args:
        event_code: The event code to register for. If None, will use a test code.
        dry_run: If True, will not actually submit the registration.
    """
    if not event_code:
        event_code = "TEST_EVENT_CODE"  # Default test code
        log.info(f"No event code provided, using test code: {event_code}")

    log.info(
        f"Testing Home Depot registration API with Playwright for event code: {event_code}"
    )

    # Registration endpoint
    url = f"https://www.homedepot.ca/api/workshopsvc/v1/workshops/WS00023/events/{event_code}/signups?lang=en"

    # Test registration data - replace with your test data
    payload = {
        "customer": {
            "firstName": "Test",
            "lastName": "User",
            "email": "test@example.com",
        },
        "workshopEventCode": event_code,
        "store": "7265",
        "participantCount": 1,
        "guestParticipants": [],
        "lang": "en",
    }

    log.info(f"Registration URL: {url}")
    log.info(f"Registration payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        log.info("DRY RUN - Registration request not sent")
        return True, "Dry run completed"

    async with async_playwright() as playwright:
        context = await playwright.request.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0"
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.homedepot.ca/workshops?store=7265",
        }

        log.info(f"Registration headers: {headers}")

        try:
            response = await context.post(
                url, headers=headers, data=json.dumps(payload)
            )

            status = response.status
            log.info(f"Registration response status code: {status}")

            resp_headers = response.headers
            log.info(f"Registration response headers: {resp_headers}")

            text_content = await response.text()
            log.info(f"Registration response length: {len(text_content)} characters")
            log.info(f"Registration response preview: {text_content[:200]}")

            if status >= 200 and status < 300:
                log.info("Registration request was successful")

                try:
                    json_content = await response.json()
                    log.info(
                        f"Registration response JSON: {json.dumps(json_content, indent=2)}"
                    )
                except json.JSONDecodeError as e:
                    log.warning(f"Failed to decode JSON registration response: {e}")

                return True, text_content
            else:
                log.error(f"Registration failed with status code {status}")
                log.error(f"Error response: {text_content[:500]}")
                return False, text_content
        except Exception as e:
            log.error(f"Registration request exception occurred: {str(e)}")
            return False, str(e)


async def main():
    """
    Run all tests
    """
    log.info("Starting Home Depot API tests...")

    # Test the workshop listing API with Playwright
    event_code = await test_playwright_api_request()

    if not event_code:
        # Try with requests if Playwright failed
        event_code = test_requests_api()

    if event_code:
        log.info(f"Found a valid event code: {event_code}")

        # Test the registration API with requests (dry run by default)
        success_req, response_req = test_registration_api(event_code)

        # Test the registration API with Playwright (dry run by default)
        success_pw, response_pw = await test_registration_api_playwright(event_code)

        log.info(
            f"Registration test with requests: {'Success' if success_req else 'Failed'}"
        )
        log.info(
            f"Registration test with Playwright: {'Success' if success_pw else 'Failed'}"
        )
    else:
        log.warning(
            "No valid event code found. Registration tests will use a dummy code."
        )

        # Test with dummy code
        await test_registration_api_playwright()
        test_registration_api()

    log.info("Tests completed")


if __name__ == "__main__":
    asyncio.run(main())
