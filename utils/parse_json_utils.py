import os

from dotenv import load_dotenv
import openai
from sec_api import XbrlApi
from utils.openai_utils import generate_guidance

load_dotenv()
# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
xbrlApi = XbrlApi(os.getenv("SEC_API_KEY"))


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
	for i in range(len(OperatingIncome)):
		if(OperatingIncome[i]['year'] != DepreciationAndAmortization[i]['year']):
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


# with clarification, i might need to change the prompt to datapromt2 if required.

def extract_from_xbrl_json(xbrl_json):
	OperatingIncome = extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['OperatingIncomeLoss']);
	ProfitLoss = extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['ProfitLoss']);
	NetIncome = extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['NetIncomeLossAvailableToCommonStockholdersBasic']);
	InterestExpense = extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['InterestIncomeExpenseNonoperatingNet']);
	IncomeTax = extract_year_and_value_in_array(xbrl_json['StatementsOfCashFlows']['IncomeTaxesPaidNet']);
	DepreciationAndAmortization = extract_year_and_value_in_array(xbrl_json['StatementsOfCashFlows']['DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts']);
	NetRevenue = extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['RevenueFromContractWithCustomerExcludingAssessedTax']);
	name = xbrl_json['CoverPage']['EntityRegistrantName'];
	ebitda = get_ebitda(OperatingIncome, DepreciationAndAmortization);
	annual_revenue_growth = get_growth_rate(NetRevenue);
	ebitda_growth = get_growth_rate(ebitda);
	year = xbrl_json['CoverPage']['DocumentFiscalYearFocus'];
	response = {
		"Operating Income": OperatingIncome,
		"Profit Loss":  ProfitLoss,     
		"Net income": NetIncome,
		"interest expense": InterestExpense,
		"Income Tax": IncomeTax,
		"Depreciation & Amortization": DepreciationAndAmortization,            
		"Net Revenue": NetRevenue,
		"name": name,
		"ebitda": ebitda,
		"annual revenue growth": annual_revenue_growth,
		"ebitda growth": ebitda_growth,
		"year": year,
	}
	# this is used to generate guidance from the extracted data. is in the openai_utils.py file
	guidance = generate_guidance(response)
	response["guidance"] = guidance

	return response


def scrape_and_get_reports(urls_array):
	print("Scraping and getting reports...")
	print(urls_array)
	report_array = []
	for url in urls_array:
		try:
			xbrl_json = xbrlApi.xbrl_to_json(htm_url=url)
		except Exception as e:
			print(f"Error extracting JSON from XBRL for URL {url}: {e}")
			
		response = extract_from_xbrl_json(xbrl_json)
		report_array.append(response)
	
	return report_array