import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pyvirtualdisplay import Display
from fake_useragent import UserAgent
no_of_pages_serp = 1
no_of_results_serp = 2

def scrape_site(url):
    print("scrapping url", url)
    driver = build_web_driver()
    print("scrapping url 1", url)
    driver.get(url)
    print("scrapping url 2", url)
    try:
        print("scrapping url 3", url)
        element_present = EC.presence_of_element_located((By.XPATH, "/html/body"))
        print("scrapping url 4", url)
        WebDriverWait(driver, 10).until(element_present)
    except TimeoutException:
        print("scrapping url 5", url)
        print("Timed out waiting for page to load")
        return "NA"
    print("scrapping completed")
    html = driver.find_element(By.XPATH, "/html/body").text
    # soup = BeautifulSoup(html, 'html.parser')
    # scraped_text = ' '.join([p.get_text() for p in soup.find_all('p')])
    driver.quit()
    return html


def build_web_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    ua = UserAgent()
    userAgent = ua.random
    print(userAgent)
    options.add_argument(f'user-agent={userAgent}')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f'user-agent={userAgent}')
    driver = webdriver.Chrome(options=options)
    return driver


def serp_scrap_results(query):

    driver = build_web_driver()

    # Set up WebDriver


    # Load Google search page
    url = 'https://www.google.com/'
    driver.get(url)
    url_array = []

    # Search for keyword
    search_box = driver.find_element(By.NAME, 'q')
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)


    # Scrape multiple pages
    for page in range(0, no_of_pages_serp):  # Scrape the first 5 pages of results
        # Wait for the search results page to load
        try:
            element_present = EC.presence_of_element_located((By.CSS_SELECTOR, '.g'))
            WebDriverWait(driver, 10).until(element_present)
        except TimeoutException:
            print("Timed out waiting for page to load")

        # Parse the search results
        search_results = driver.find_elements(By.CSS_SELECTOR, '.g')
        del search_results[no_of_results_serp:]
        for result in search_results:
            link = result.find_element(By.CSS_SELECTOR, 'a').get_attribute('href').split('#')[0]
            url_array.append(link)

        # Click on the next page
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '#pnnext')
            next_button.click()
        except:
            break
    driver.quit()
    return url_array
    # Close the WebDriver
