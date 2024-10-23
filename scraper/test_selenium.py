from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from time import sleep
import platform


# Set up options for headless Chrome
options = Options()
options.headless = True  # Enable headless mode for invisible operation
options.add_argument("--window-size=1920,1200")  # Define the window size of the browser
options.add_argument("--headless")  # Run in headless mode
options.add_argument("--no-sandbox")  # Bypass OS security model
options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36")
options.add_argument("--disable-gpu")  # Disable GPU acceleration
options.add_argument("--window-size=1920,1080")  # Set window size


# Set the path to the Chromedriver
DRIVER_PATH = '/usr/bin/chromedriver'

# Check if the operating system is macOS
if platform.system() == 'Darwin':  # macOS
    DRIVER_PATH = '/opt/homebrew/bin/chromedriver'

# Initialize Chrome with the specified options
driver = webdriver.Chrome(options=options)

# Navigate to the Nintendo website
try:
    driver.get("https://www.costco.ca/aiden-%2526-ivy-6-piece-fabric-sectional%2c-grey.product.4000207338.html?langId=-24&province=SK&sh=true&nf=true")
    sleep(5)
    try:
        cookie_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        cookie_button.click()
    except Exception as e:
        print("No cookie consent prompt found or an error occurred:", e)
    sleep(3)

    # Wait for the "Change Delivery Postal Code" link to be present and click it
    change_zip_code_link = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#out-of-stock-zip-code + a"))
    )
    change_zip_code_link.click()

    # Wait for the zip code input field to be present and fill it
    zip_code_field = WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.ID, "eddZipCodeField"))
    )
    zip_code_field.clear()  # Clear any pre-filled text
    zip_code_field.send_keys("S7T 0J6")  # Fill in the zip code

    # Wait for the submit button to be clickable and click it
    submit_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.ID, "edd-check-button"))
    )
    submit_button.click()
    sleep(1)

    # Wait for the "add-to-cart" input button to be present
    add_to_cart_button = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "add-to-cart-btn"))
    )

    # Retrieve the value of the button
    button_value = add_to_cart_button.get_attribute("value")
    # Now get the price from the specified element
    price_element = WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#pull-right-price .value"))
    )
    price = price_element.text
    print(f"The price of the item is: ${price}")

    # Check if the value indicates out of stock
    if button_value.lower() == "out of stock":
        print("The item is out of stock.")
    else:
        print("The item is available.")
finally:
    # Output the page source to the console
    # print(driver.page_source)

    # Close the browser session cleanly to free up system resources
    driver.quit()
