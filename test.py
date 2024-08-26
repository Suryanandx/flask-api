import json
from bs4 import BeautifulSoup

def extract_net_revenue_from_xbrl(xbrl_file_path, output_file_path):
    # Open and read the XBRL file
    with open(xbrl_file_path, 'r') as file:
        content = file.read()

    # Parse the XBRL using BeautifulSoup with the lxml XML parser
    soup = BeautifulSoup(content, features="xml")

    # Define the tags and their output names
    tag_mapping = {
        'Depreciation & Amortization': [
            'DepreciationDepletionAndAmortizationExcludingAmortizationOfDebtIssuanceCosts',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'DepreciationAndAmortization',
            'DepreciationAmortizationAndAccretionNet',
            'DepreciationAmortization',
            'Amortization'
        ],
        'Income Tax': [
            'IncomeTaxesPaidNet',
            'IncomeTaxExpenseBenefit',
            'IncomeTax'
        ],
        'Net Revenue': [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
            'SalesRevenueNet',
            'Revenue',
            'TotalRevenue'
        ],
        'Net Income': [
            'NetIncomeLossAttributableToParentBeforeAccretionOfRedeemableNoncontrollingInterest',
            'NetIncomeLoss',
            'NetIncome',
            'IncomeLoss'
        ],
        'Operating Income': [
            'OperatingIncomeLoss',
            'OperatingProfitLoss',
            'OperatingIncome'
        ],
        'Profit Loss': [
            'ProfitLoss',
            'ComprehensiveIncomeNetOfTax',
            'NetProfit'
        ],
        'Interest Expense': [
            'InterestIncomeExpenseNonoperatingNet',
            'InterestExpense',
            'InterestIncome'
        ],
        'name': [
            'EntityRegistrantName',
            'CompanyName'
        ],
        'year': [
            'DocumentFiscalYearFocus',
            'FiscalYear'
        ]
    }

    def extract_data(tag_names):
        for tag_name in tag_names:
            elements = soup.find_all(tag_name)
            if elements:
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
        return None  # Return None if no data was found for any of the tag names

    # Collect data for all tags
    financial_data = {}
    for output_name, tag_names in tag_mapping.items():
        financial_data[output_name] = extract_data(tag_names) or []

    # Save the output to a JSON file
    with open(output_file_path, 'w') as json_file:
        json.dump(financial_data, json_file, indent=4)

    print(f"Data successfully saved to {output_file_path}")

# Example usage:
xbrl_file_path = r"xmls/d600678d10k_htm.xml"
output_file_path = "output.json"
extract_net_revenue_from_xbrl(xbrl_file_path, output_file_path)
