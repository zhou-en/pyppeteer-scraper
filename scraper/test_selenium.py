from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# Set the path to the installed Chromium driver
DRIVER_PATH = '/usr/bin/chromedriver'

# Set up the Service
service = Service(DRIVER_PATH)

# Set Chrome options for headless mode (if needed)
options = webdriver.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--headless')  # Optional: Run in headless mode if desired
options.binary_location = "/usr/bin/chromium-browser"  # Path to Chromium browser

# Initialize the Chrome WebDriver with Chromium
driver = webdriver.Chrome(service=service, options=options)

# Example: Open a website
driver.get("https://www.google.com")
print(driver.title)
