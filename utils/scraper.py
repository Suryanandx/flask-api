import requests
from bs4 import BeautifulSoup
import re

def find_google_finance_link(company_name):
    query = f"{company_name} googlefinance"
    search_url = f"https://www.google.com/search?q={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    }
    
    response = requests.get(search_url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if "https://www.google.com/finance/quote/" in href:
                return href.split("&")[0]  
    return None


def get_stock_price(google_finance_url):
    response = requests.get(google_finance_url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_div = soup.find('div', class_='YMlKec fxKbKc')
        if price_div:
            return price_div.text.strip()
        else:
            return "Price not found"
    else:
        return f"Failed to retrieve data. Status code: {response.status_code}"

def get_stock_price_by_company_name(company_name):
    google_finance_url = find_google_finance_link(company_name)
    if google_finance_url:
        return get_stock_price(google_finance_url)
    else:
        return f"Google Finance link for {company_name} not found."