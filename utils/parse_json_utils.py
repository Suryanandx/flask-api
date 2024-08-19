import os
from dotenv import load_dotenv
import openai
from sec_api import XbrlApi
from utils.openai_utils import generate_guidance, generate_expanalysis, analysis_from_html, analysis_10k_json
from utils.web_scrapper import serp_scrap_results, scrape_site
import json
import subprocess
import openai
import requests
from bs4 import BeautifulSoup


load_dotenv()
# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
xbrlApi = XbrlApi(os.getenv("SEC_API_KEY"))
product_and_countries_query = "What are the top countries the company has performed well?  what are the top performing products of the company? the response should be two arrays, one for list of countries and another one for list of products"


def extract_year_and_value_in_array(data):
    results = []
    for entry in data:
        if 'segment' not in entry:
            end_date = entry['period']['endDate']
            year = end_date.split('-')[0]
            value = entry['value']
            results.append({"year": year, "value": value})
    return results

def get_ebitda(OperatingIncome, DepreciationAndAmortization):
	ebitda = []
	len_of_dep = len(DepreciationAndAmortization);
	len_of_optinc = len(OperatingIncome)
	range_of_data = range(min(len_of_optinc, len_of_dep))
	print(range_of_data, 'range(len(OperatingIncome))')
	for i in range_of_data:
		if(i in OperatingIncome and i in DepreciationAndAmortization):
			if (OperatingIncome[i]['year'] != DepreciationAndAmortization[i]['year']):
				print("Error: Operating Income and Depreciation and Amortization years do not match");
				continue;
		ebitda.append({"year": OperatingIncome[i]['year'], "value": str(int(OperatingIncome[i]['value']) + int(DepreciationAndAmortization[i]['value']))})
	return ebitda

def get_growth_rate(data):
	growth = []
	for i in range(0, len(data)-1):
		# Assuming data is sorted in descending order of consecutive years
		growth.append({"year": data[i]['year'], "value": str(100*(int(data[i]['value']) - int(data[i+1]['value']))/int(data[i+1]['value'])) + " %"})

	return growth
def get_operating_income_from_json(xbrl_json):
	value = xbrl_json['StatementsOfIncome']['OperatingIncomeLoss'];
	yearValue = extract_year_and_value_in_array(value)
	return yearValue

def get_profit_loss(xbrl_json):
	value = xbrl_json['StatementsOfIncome']['ProfitLoss']
	yearValue = extract_year_and_value_in_array(value)
	return yearValue

def get_net_income(xbrl_json):
	if 'NetIncomeLossAvailableToCommonStockholdersBasic' in  xbrl_json['StatementsOfIncome'] :
		value = xbrl_json['StatementsOfIncome']['NetIncomeLossAvailableToCommonStockholdersBasic']
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	elif 'NetIncomeLoss' in xbrl_json['StatementsOfIncome']:
		value = xbrl_json['StatementsOfIncome']['NetIncomeLoss'];
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	else:
		value = "NA"
		return value


# with clarification, i might need to change the prompt to datapromt2 if required.

def get_interest_expense(xbrl_json):
	if 'InterestIncomeExpenseNonoperatingNet' in  xbrl_json['StatementsOfIncome'] :
		value = xbrl_json['StatementsOfIncome']['InterestIncomeExpenseNonoperatingNet'];
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	elif 'InterestExpense' in xbrl_json['FinancialExpensesNetScheduleOfFinancialExpensesDetail']:
		value = xbrl_json['FinancialExpensesNetScheduleOfFinancialExpensesDetail']['InterestExpense'];
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	else:
		print("returning 3", "NA")
		value = "NA"
		return value

def get_dep_amort(xbrl_json):
	if 'DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts' in  xbrl_json['StatementsOfCashFlows'] :
		value = xbrl_json['StatementsOfCashFlows']['DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts']
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	elif 'DepreciationAndAmortization' in xbrl_json['StatementsOfCashFlows']:
		value =  xbrl_json['StatementsOfCashFlows']['DepreciationAndAmortization'] ;
		yearValue = extract_year_and_value_in_array(value)
		return yearValue
	else:
		value = "NA"
		return value


def extract_from_xbrl_json(xbrl_json, project_id):

	response = {
		"Operating Income": xbrl_json["Operating Income"],
		"Profit Loss":  xbrl_json["Profit Loss"],
		"Net income": xbrl_json["Net income"],
		"interest expense": xbrl_json["interest expense"],
		"Income Tax": xbrl_json["Income Tax"],
		"Depreciation & Amortization": xbrl_json["Depreciation & Amortization"],
		"Net Revenue": xbrl_json["Net Revenue"],
		"name": xbrl_json["name"],
		"ebitda": xbrl_json["ebitda"],
		"annual revenue growth": xbrl_json["annual revenue growth"],
		"ebitda growth": xbrl_json["ebitda growth"],
		"year": xbrl_json["year"],
	}

	# this is used to generate guidance from the extracted data. is in the openai_utils.py file
	serp_scrapped_urls_method_a = serp_scrap_results(name + " Analysis " + year);
	serp_scrapped_urls_method_b = serp_scrap_results(name + " most profitable products and countries ");
	serp_scrapped_urls_method_c = serp_scrap_results(name + " Earnings call " + year);
	serp_scrapped_urls = serp_scrapped_urls_method_a + list(set(serp_scrapped_urls_method_b) - set(serp_scrapped_urls_method_a))
	serp_scrapped_urls = serp_scrapped_urls + list(set(serp_scrapped_urls_method_c) - set(serp_scrapped_urls))

	print(serp_scrapped_urls, 'serp_scrapped_urls')
	scraped_data = []
	for url in serp_scrapped_urls:
		# Scrape each website with a timeout of 60 seconds
		try:
			current_scrapped_text = scrape_site(url)
			scraped_data.append(current_scrapped_text)
		except Exception as e:
			print("Couldn't scrap the site")
			scraped_data.append("NA")

	# Join scraped data from all URLs into a single text
	all_scraped_data = ' '.join(scraped_data)

	# with AI
	result_from_analysis = analysis_10k_json(response, all_scraped_data, project_id, name)
	response['scrapped_data'] = all_scraped_data

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

	response['products'] = products_array
	response['countries'] = countries_object
	response["guidance"] = result_from_analysis['guidance']
	response["note"] = result_from_analysis['expert_analysis']
	print("response is ready", response)

    # without ai
	# response['products_and_countries'] = all_scraped_data
	# response["guidance"] = "guidance"
	# response["note"] = "note"

	return response


def xbrl_to_json(urls_array):
	json_array = []
	for url in urls_array:
		try:
			xbrl_json_item = extract_net_revenue_from_xbrl(htm_url=url)
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
        'InterestIncomeExpenseNonoperatingNet': 'Interest Expense'
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

def scrape_and_get_reports(json_array, project_id):
	print("Scraping and getting reports...")
	report_array = []
	for json_item in json_array:
		response = extract_from_xbrl_json(json_item['response'], project_id)
		report_array.append(response)
	
	return report_array