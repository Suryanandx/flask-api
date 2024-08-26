import json
from bs4 import BeautifulSoup

def extract_net_revenue_from_xbrl(xbrl_file_path):
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
            'Amortization',
            'Depreciation',
            'Accretion',
            'AmortizationExpense'
        ],
        'Income Tax': [
            'IncomeTaxesPaidNet',
            'IncomeTaxExpenseBenefit',
            'IncomeTax',
            'IncomeTaxExpense',
            'IncomeTaxBenefit',
            'IncomeTaxPayable',
            'TaxExpense'
        ],
        'Net Revenue': [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
            'SalesRevenueNet',
            'Revenue',
            'TotalRevenue',
            'NetSales',
            'GrossRevenue'
        ],
        'Net Income': [
            'NetIncomeLossAttributableToParentBeforeAccretionOfRedeemableNoncontrollingInterest',
            'NetIncomeLoss',
            'NetIncome',
            'IncomeLoss',
            'NetEarnings',
            'EarningsAfterTax'
        ],
        'Operating Income': [
            'OperatingIncomeLoss',
            'OperatingProfitLoss',
            'OperatingIncome',
            'OperatingProfit',
            'IncomeFromOperations'
        ],
        'Profit Loss': [
            'ProfitLoss',
            'ComprehensiveIncomeNetOfTax',
            'NetProfit',
            'NetEarningsLoss',
            'ProfitOrLoss',
            'ComprehensiveIncome'
        ],
        'Interest Expense': [
            'InterestIncomeExpenseNonoperatingNet',
            'InterestExpense',
            'InterestIncome',
            'InterestCost',
            'InterestCharges',
            'InterestExpenseNet'
        ],
        'name': [
            'EntityRegistrantName',
            'CompanyName',
            'IssuerName',
            'EntityName'
        ],
        'year': [
            'DocumentFiscalYearFocus',
            'FiscalYear',
            'YearOfReport',
            'ReportingYear',
            'YearEnd'
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

    return financial_data


# Example usage:
xbrl_file_path = r"xmls/rprx-20231231_htm.xml"
extract_net_revenue_from_xbrl(xbrl_file_path)
