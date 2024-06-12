def extract_year_and_value_in_array(data):
    results = []
    for entry in data:
        if 'segment' not in entry:
            end_date = entry['period']['endDate']
            year = end_date.split('-')[0]
            value = entry['value']
            results.append({"year": year, "value": value})
    return results

def extract_from_xbrl_json(xbrl_json):
    response = {
        "Operating Income": extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['OperatingIncomeLoss']),
        "Profit Loss":  extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['ProfitLoss']),     
        "Net income": extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['NetIncomeLossAvailableToCommonStockholdersBasic']),
        "interest expense": extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['InterestIncomeExpenseNonoperatingNet']),
        "Income Tax": extract_year_and_value_in_array(xbrl_json['StatementsOfCashFlows']['IncomeTaxesPaidNet']),
        "Depreciation & Amortization": extract_year_and_value_in_array(xbrl_json['StatementsOfCashFlows']['DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts'])  ,            
        "Net Revenue": extract_year_and_value_in_array(xbrl_json['StatementsOfIncome']['RevenueFromContractWithCustomerExcludingAssessedTax']),
        "name": xbrl_json['CoverPage']['EntityRegistrantName'],
        "ebitda": 0,
        "annual revenue growth": 0,
        "ebitda growth": 0,
        "guidance": 0,
        "year": xbrl_json['CoverPage']['DocumentFiscalYearFocus'],
    }
    return response