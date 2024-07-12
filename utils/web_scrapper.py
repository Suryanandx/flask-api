import os
import openai
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
from utils.text_utils import get_or_create_vector_store, split_text_by_tokens
from langchain.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter

no_of_pages_serp = 1
no_of_results_serp = 10

def scrape_site(url):
    scraped_text = ""
    try:
        print("scrapping url", url)
        driver = build_web_driver()
        if driver is not None:
            print("scrapping url 1", url)
            driver.get(url)
            print("scrapping url 2", url)
            print("scrapping url 3", url)
            element_present = EC.presence_of_element_located((By.XPATH, "/html/body"))
            print("scrapping url 4", url)
            WebDriverWait(driver, 10).until(element_present)
            html = driver.find_element(By.XPATH, "/html/body").text
            soup = BeautifulSoup(html, 'html.parser')
            scraped_text = ' '.join([p.get_text() for p in soup.find_all('p')])
            print("scrapping url 5", url)
            driver.quit()
        else:
            scraped_text += "NA"
    except TimeoutException:
        print("Timed out waiting for page to load")
        scraped_text += "NA"
    print("scrapping completed")

    # print(html, 'html')
    # refined_text = __refine_text(html)
    # print(refined_text)
    return scraped_text


def build_web_driver():
    try:
        # Set up WebDriver (1)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        display = Display(visible=0, size=(1920, 1080))
        display.start()
        ua = UserAgent()
        userAgent = ua.random
        print(userAgent)
        options.add_argument(f'user-agent={userAgent}')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f'user-agent={userAgent}')
        options.add_argument("--no-sandbox")
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1420,1080')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument("--disable-notifications")
        options.add_argument("--remote-debugging-port=9222")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("excludeSwitches", ["disable-popup-blocking"])

        driver = webdriver.Chrome(options=options)

        return driver
    except TimeoutException:
        print("Timed out waiting for page to load")
        return None

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

def __refine_text(text):
    openai.api_key = os.environ["OPENAI_API_KEY"]
    prompt_context = '''
    We have also extracted following text information from a website:\n
    '''
    prompt_context += text

    prompt = '''\n
       You are a highly experienced text analyst with a rich history of over 30 years in the field. The company you work for has acqurired textual information that needs to be cleaned and refined. The text is extracted from various websites and contains irrelevant information. Your task is to refine the text and provide a clean version of the text.
       Specifically, if there are the following types of conent please remove them:
        1. **Advertisements and Promotional Content**: Any content aimed at selling products, services, or promoting the website itself.
        2. **Navigation Links and Menus**: Links to other sections of the website that do not add to the main content.
        3. **Disclaimers and Legal Notices**: Standard disclaimers or legal information not pertinent to the main content.
        4. **Generic Greetings and Intros**: Standard greetings, intros, or welcome messages that do not contribute to the core information.
        5. **Social Media Links and Share Buttons**: Links to follow on social media or share the content.
        6. **Subscription Prompts**: Requests for readers to subscribe to newsletters or updates.
        7. **Contact Information**: General contact information that does not relate to the main content.
        8. **Boilerplate Text**: Standardized text that is repeated across multiple pages without specific relevance to the current content.
        
        However, it is crucial to retain all important information related to the main topic.That includes facts, figures, statistics, analysis, and any other relevant data. If not all the types of content mentioned above are present, can be ignore the ones that are not relevant. But do not remove any relevant content in order to follow the above rules.
        Also the most important rule is to ensure that the refined text follows the same structure and flow as the original text. There shouldnt be any change in the meaning of the text.\n
        Do not try to rewrite or rearrange or paraphrase the text. Just remove the irrelevant content. This is not a creative writing task, just a task to remove irrelevant content.
       '''
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )

    chunks = text_splitter.split_text(text=prompt_context)
    print("chunks ready")
    vector_store = get_or_create_vector_store(chunks, store_name="vector_store")
    print("vector store ready")
    docs = vector_store.similarity_search(query=prompt, k=3)
    print("docs ready")
    llm = OpenAI(temperature=0.7, model="gpt-3.5-turbo-instruct")
    print("llm ready")
    chain = load_qa_chain(llm=llm, chain_type="stuff")
    print("chain loaded")

    with get_openai_callback() as cb:
        response = chain.run(input_documents=docs, question=prompt)

    return response
