import logging
import os
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from bs4 import BeautifulSoup

# Load environment variables from a .env file
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database()  # You might need to specify the database name

# Configure logging
logging.basicConfig(level=logging.INFO)


def extract_net_revenue_from_xbrl(xbrl_file_path):
    try:
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

        def extract_data(tag1_names):
            for tag_name in tag1_names:
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
    except Exception as e:
        logging.error(f"Error extracting data from XBRL file {xbrl_file_path}: {e}")
        return None


def process_xbrl_files(file1_paths):
    json_array = []
    for file_path in file1_paths:
        try:
            xbrl_json_item = extract_net_revenue_from_xbrl(file_path)
            if xbrl_json_item is not None:
                json_array.append(xbrl_json_item)
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
    return json_array


def save_to_mongodb(project1_name, project1_description, comps1, xbrl1_json):
    try:
        project_data = {
            "name": project1_name,
            "description": project1_description,
            "comps": comps1,
            "xbrl_json": xbrl1_json
        }

        result1 = db.projects.insert_one(project_data)
        inserted_id = result1.inserted_id

        inserted_document = db.projects.find_one({"_id": ObjectId(inserted_id)})
        inserted_document["_id"] = str(inserted_document["_id"])

        return inserted_document
    except Exception as e:
        logging.error(f"Error saving project data to MongoDB: {e}")
        return None


# Example usage
if __name__ == "__main__":
    file_paths = ["xmls/amrx-20231231_htm.xml", "xmls/rprx-20231231_htm.xml"]
    project_name = "Sample Project"
    project_description = "This is a sample project description."
    comps = [{"files": [{"filename": "file1.xbrl"}]}, {"files": [{"filename": "file2.xbrl"}]}]

    xbrl_json = process_xbrl_files(file_paths)
    result = save_to_mongodb(project_name, project_description, comps, xbrl_json)
    if result:
        print("Project saved successfully:", result)
    else:
        print("Failed to save project.")
