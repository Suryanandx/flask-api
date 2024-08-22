import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sec_api import XbrlApi
import logging
from utils.openai_utils import analysis_10k_json
from utils.web_scrapper import serp_scrap_results, scrape_site
from concurrent.futures import ProcessPoolExecutor

load_dotenv()
# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
xbrlApi = XbrlApi(os.getenv("SEC_API_KEY"))
product_and_countries_query = "What are the top countries the company has performed well?  what are the top performing products of the company? the response should be two arrays, one for list of countries and another one for list of products"

from collections import defaultdict
max_pool_workers = int(os.getenv("MAX_POOL_WORKERS"))


def extract_latest_year_data(xbrl_json):
    # Extract the financial data and find the latest year
    year_wise_data = defaultdict(lambda: defaultdict(lambda: 0))

    # Iterate through each key in the xbrl_json
    for key, values in xbrl_json.items():
        for entry in values:
            year = entry.get('year')
            value_str = entry.get('value', "0")  # Get value as string
            try:
                value = int(value_str)  # Attempt to convert to integer
            except ValueError:
                value = 0  # If conversion fails, default to 0
            year_wise_data[year][key] += value  # Sum up values per year

    # Convert to regular dict and find the latest year
    year_wise_data = {year: dict(data) for year, data in year_wise_data.items()}
    latest_year = max(year_wise_data.keys())

    return year_wise_data, latest_year


def calculate_financials(xbrl_json):
    year_wise_data, latest_year = extract_latest_year_data(xbrl_json)

    # Get the latest year and previous year
    latest_year_data = year_wise_data[latest_year]
    previous_year = str(int(latest_year) - 1)
    previous_year_data = year_wise_data.get(previous_year, {})

    # Calculate Revenue Growth
    latest_revenue = latest_year_data.get("Net Revenue", 0)
    previous_revenue = previous_year_data.get("Net Revenue", 0)
    if previous_revenue:
        revenue_growth = ((latest_revenue - previous_revenue) / previous_revenue) * 100
    else:
        revenue_growth = None  # Unable to calculate growth without previous data

    # Calculate EBITDA (Operating Income + Depreciation & Amortization)
    latest_operating_income = latest_year_data.get("Operating Income", 0)
    latest_depreciation_amortization = latest_year_data.get("Depreciation & Amortization", 0)
    latest_ebitda = latest_operating_income + latest_depreciation_amortization

    # Calculate EBITDA Growth
    previous_operating_income = previous_year_data.get("Operating Income", 0)
    previous_depreciation_amortization = previous_year_data.get("Depreciation & Amortization", 0)
    previous_ebitda = previous_operating_income + previous_depreciation_amortization

    if previous_ebitda:
        ebitda_growth = ((latest_ebitda - previous_ebitda) / previous_ebitda) * 100
    else:
        ebitda_growth = None  # Unable to calculate growth without previous data

    return {
        "annual revenue growth": [{
            "year": latest_year,
            "value": revenue_growth
        }] if revenue_growth is not None else [],
        "ebitda": [{
            "year": latest_year,
            "value": latest_ebitda
        }],
        "ebitda growth": [{
            "year": latest_year,
            "value": ebitda_growth
        }] if ebitda_growth is not None else []
    }


def get_latest_year(year_wise_data):
    # Convert the year keys to integers and find the maximum year
    years = [int(year) for year in year_wise_data.keys()]
    latest_year = max(years)

    return str(latest_year)


def get_company_name(year_wise_data):
    # Iterate through the year-wise data
    for year, data in year_wise_data.items():
        # Check if the 'name' key exists in the current year's data
        if 'name' in data:
            return data['name']

    # If the 'name' key is not found in any year, return a default value
    return "Company name not found"


def extract_year_wise_data(xbrl_json):
    year_wise_data = defaultdict(lambda: defaultdict(lambda: "Value not available"))

    # Extract the company name if available
    company_name = xbrl_json.get("name", [{"value": "Unknown Company"}])[0].get("value", "Unknown Company")

    # Iterate through each key in the xbrl_json
    for key, values in xbrl_json.items():
        for entry in values:
            year = entry.get('year')
            value = entry.get('value', "Value not available")
            year_wise_data[year][key] = value
            # Add company name and year to each year's data
            year_wise_data[year]["name"] = company_name
            year_wise_data[year]["year"] = year

    # Convert defaultdict to a regular dict for the final output
    year_wise_data = {year: dict(data) for year, data in year_wise_data.items()}

    return year_wise_data


def summarize_data(year_wise_data):
    summary = []

    for year, data in year_wise_data.items():
        summary.append(f"Summary for {data['name']} in {year}:")
        summary.append(f"- Net Revenue: {data.get('Net Revenue', 'Value not available')}")
        summary.append(f"- Operating Income: {data.get('Operating Income', 'Value not available')}")
        summary.append(f"- Net Income: {data.get('Net Income', 'Value not available')}")
        summary.append(f"- Profit Loss: {data.get('Profit Loss', 'Value not available')}")
        summary.append(f"- Income Tax: {data.get('Income Tax', 'Value not available')}")
        summary.append(
            f"- Depreciation & Amortization: {data.get('Depreciation & Amortization', 'Value not available')}")
        summary.append(f"- Interest Expense: {data.get('Interest Expense', 'Value not available')}")
        summary.append("")  # Add a blank line between year summaries

    return "\n".join(summary)


def scrape_url(url):
    try:
        return scrape_site(url)
    except Exception as e:
        logging.error(f"Couldn't scrap the site: {str(e)}", exc_info=True)
        return "NA"


def extract_from_xbrl_json(xbrl_json, project_id):
    json_from_xbrl = extract_year_wise_data(xbrl_json)
    response = summarize_data(json_from_xbrl)
    company_name = get_company_name(json_from_xbrl)
    latest_year = get_latest_year(json_from_xbrl)
    financials = calculate_financials(xbrl_json)
    xbrl_json["ebitda"] = financials["ebitda"]
    xbrl_json["annual revenue growth"] = financials["annual revenue growth"]
    xbrl_json["ebitda growth"] = financials["ebitda growth"]

    # this is used to generate guidance from the extracted data. is in the openai_utils.py file
    serp_scrapped_urls_method_a = serp_scrap_results(company_name + " Analysis for the year " + latest_year);
    serp_scrapped_urls_method_b = serp_scrap_results(
        company_name + " most profitable products and countries for the year " + latest_year);
    serp_scrapped_urls_method_c = serp_scrap_results(company_name + " Earnings call for the year " + latest_year);
    serp_scrapped_urls = serp_scrapped_urls_method_a + list(
        set(serp_scrapped_urls_method_b) - set(serp_scrapped_urls_method_a))
    serp_scrapped_urls = serp_scrapped_urls + list(set(serp_scrapped_urls_method_c) - set(serp_scrapped_urls))

    # Filtering URLs
    filtered_urls = [url for url in serp_scrapped_urls if not url.endswith(".pdf")]

    print(filtered_urls, 'serp_scrapped_urls')
    scraped_data = []

    max_workers = max(max_pool_workers, multiprocessing.cpu_count())  # Use fewer processes to reduce load

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_url, url): url for url in filtered_urls}
        for future in as_completed(future_to_url):
            scraped_data.append(future.result())

    # Join scraped data from all URLs into a single text
    all_scraped_data = ' '.join(scraped_data)

    # with AI
    result_from_analysis = analysis_10k_json(response, all_scraped_data, project_id, company_name)
    xbrl_json['scrapped_data'] = all_scraped_data

    print("result_from_analysis", result_from_analysis)
    products_array = []
    for product in result_from_analysis['products']:
        current_product = {
            "name": product,
            "type": "other"
        }
        products_array.append(current_product)
    print("products built", products_array)

    countries_object = {}
    for idx, country in enumerate(result_from_analysis['countries']):
        countries_object[country] = idx
    print("countries built", countries_object)

    xbrl_json['products'] = products_array
    xbrl_json['countries'] = countries_object
    xbrl_json["guidance"] = result_from_analysis['guidance']
    xbrl_json["note"] = result_from_analysis['expert_analysis']
    xbrl_json["name"] = company_name
    xbrl_json["year"] = latest_year
    print("response is ready", xbrl_json)

    return xbrl_json


def xbrl_to_json(urls_array):
    json_array = []
    for url in urls_array:
        try:
            xbrl_json_item = extract_net_revenue_from_xbrl(url)
            json_array.append(xbrl_json_item)
        except Exception as e:
            print(f"Error extracting JSON from XBRL for URL {url}: {e}")

    return json_array


def extract_net_revenue_from_xbrl(xbrl_file_path):
    # Open and read the XBRL file
    with open(xbrl_file_path, 'r') as file:
        content = file.read()

    # Parse the XBRL using BeautifulSoup with the lxml XML parser
    soup = BeautifulSoup(content, features="xml")

    # Define the tags and their output names
    tag_mapping = {
        'DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts': 'Depreciation & Amortization',
        'IncomeTaxesPaidNet': 'Income Tax',
        'RevenueFromContractWithCustomerExcludingAssessedTax': 'Net Revenue',
        'NetIncomeLossAttributableToParentBeforeAccretionOfRedeemableNoncontrollingInterest': 'Net Income',
        'OperatingIncomeLoss': 'Operating Income',
        'ProfitLoss': 'Profit Loss',
        'InterestIncomeExpenseNonoperatingNet': 'Interest Expense',
        "EntityRegistrantName": "name",
        "DocumentFiscalYearFocus": "year"
    }

    def extract_data(tag_name):
        elements = soup.find_all(tag_name)
        data = []
        for element in elements:
            context_ref = element.get('contextRef')
            if context_ref:
                context = soup.find('context', {'id': context_ref})
                period = context.find('period') if context else None
                year = period.find('endDate').text[:4] if period else None
            else:
                year = None

            data.append({
                'value': element.text.strip(),
                'year': year
            })

        return data

    # Collect data for all tags
    financial_data = {}
    for tag, output_name in tag_mapping.items():
        financial_data[output_name] = extract_data(tag)

    return financial_data


def process_json_item(index, json_item, project_id):
    result = extract_from_xbrl_json(json_item, project_id)
    return index, result  # Ensure it returns a tuple with two values


def scrape_and_get_reports(json_array, project_id):
    print("Scraping and getting reports...")

    if not json_array:
        raise ValueError("The input json_array is empty.")

    report_array = [None] * len(json_array)

    cpu_cores = multiprocessing.cpu_count()
    max_workers = max(max_pool_workers, min(cpu_cores, len(json_array)))

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_json_item, idx, json_item, project_id): idx for idx, json_item in
                   enumerate(json_array)}

        for future in futures:
            idx, result = future.result()  # Expecting a tuple (index, result)
            report_array[idx] = result

    return report_array
