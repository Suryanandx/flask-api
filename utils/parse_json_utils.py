import os
from dotenv import load_dotenv
import openai
from sec_api import XbrlApi
from utils.openai_utils import generate_guidance, generate_expanalysis

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


def extract_from_xbrl_json(xbrl_json):
	OperatingIncome = get_operating_income_from_json(xbrl_json);
	ProfitLoss = get_profit_loss(xbrl_json);
	NetIncome = get_net_income(xbrl_json);
	InterestExpense = get_interest_expense(xbrl_json)
	IncomeTax = extract_year_and_value_in_array(xbrl_json['StatementsOfCashFlows']['IncomeTaxesPaidNet']);
	DepreciationAndAmortization = get_dep_amort(xbrl_json);
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
	note = generate_expanalysis(response)
	response["note"] = note

	return response
def xbrl_to_json(urls_array):
	json_array = []
	for url in urls_array:
		try:
			xbrl_json_item = xbrlApi.xbrl_to_json(htm_url=url)
			json_array.append(xbrl_json_item)
		except Exception as e:
			print(f"Error extracting JSON from XBRL for URL {url}: {e}")

	return json_array

def scrape_and_get_reports(json_array):
	print("Scraping and getting reports...")
	report_array = []
	for json_item in json_array:
		response = extract_from_xbrl_json(json_item['response'])
		report_array.append(response)
	
	return report_array