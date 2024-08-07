import json
import logging
import os
import subprocess
from bson import ObjectId

import openai

from utils.pdf_utils import process_pdf
from utils.text_utils import get_or_create_vector_store, split_text_by_tokens
from langchain.llms import OpenAI
from langchain.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter


def count_tokens(messages):
    return sum(len(message['content'].split()) for message in messages)

def truncate_chat_history(chat_history, max_tokens=3000):
    while count_tokens(chat_history) > max_tokens:
        chat_history.pop(4)
    return chat_history


def append_guidance_analysis_chat(db, new_guidance_from_user, existing_guidance, project_id, company_index, version_index, project):
    try:
        current_company_report = project["report"][version_index]["report"][company_index]
        logging.info(f"extracting guidance for : {str(current_company_report['name'])}")
        prompt_context = f"The company {current_company_report['name']} has the following financial data:\n"
        for key, value in current_company_report.items():
            if key != 'scrapped_data' and key != 'name':
                prompt_context += f"{key}: {value}\n"

        prompt_context += '''
        We have also extracted following text information from few websites:\n
        '''
        prompt_context += current_company_report['scrapped_data']

        chat_history = []


        if "guidance_chat" in current_company_report.keys():
            chat_history = current_company_report["guidance_chat"]
        else:
            chat_history.append({
                "role": "system",
                "content": '''
                  When writing the guidance, consider the following instructions:
                  Begin by reviewing the company's strategic objectives and financial goals. Understand what the company aims to achieve in terms of revenue, profitability, market share, etc.
                  Utilize historical financial data, market trends, and internal forecasts to project future financial performance. This includes revenue growth, cost trends, margins, and cash flow expectations.
                  Evaluate external factors that could impact financial performance, such as economic conditions, industry trends, regulatory changes, and competitive dynamics. Incorporate these into your projections.
                  Based on your analysis, create detailed projections for key financial metrics. This typically includes revenue, earnings per share (EPS), operating income, margins, capital expenditures, and other relevant financial indicators.
                  Clearly state the assumptions underlying your projections. This could include assumptions about market conditions, customer demand, pricing trends, production costs, currency fluctuations, and any other factors affecting financial outcomes.
                  Consider providing a range of potential outcomes or scenarios rather than a single point estimate. This acknowledges uncertainty and helps investors understand the range of possible results based on different assumptions or market conditions.
                  Avoid overly optimistic projections. It's crucial to be transparent and realistic about the challenges and risks the company may face in achieving its financial goals.
                  Write the financial guidance in a clear, understandable manner. Avoid jargon or overly technical language that could confuse investors.
                  Ensure that the financial guidance aligns with the company's overall strategic plan and is supported by reliable data and analysis. Review the guidance with key stakeholders, such as senior management and the board of directors, to validate assumptions and projections.
                  Once finalized, communicate the financial guidance through appropriate channels, such as regulatory filings (e.g., SEC filings), investor presentations, press releases, or conference calls. Be prepared to address questions and provide additional context as needed.
                  Continuously monitor actual performance against the guidance provided. If there are material changes or developments, consider updating the guidance to reflect new information or revised expectations.

                   For calculating the projected yearly EBITDA, consider the following factors:
                  First subtract Net sales from the cost of raw materials. Net sales are the sum of all the products sold in the company over a specific period. The costs of raw materials are the amount the paid to acquire raw materials to produce their goods.
                  Next, subtract employee costs from the result. Employee costs include salaries, wages, and benefits paid to employees.
                  Finally, subtract other operating expenses from the result. Other operating expenses include rent, utilities, insurance, and other costs associated with running the business.
                  The final figure is the projected yearly EBITDA. EBITDA stands for Earnings Before Interest, Taxes, Depreciation, and Amortization. It is a measure of a company's operating performance.

                  For calculating the projected adjusted diluted EPS, consider the following factors:
                  First take a company's net income and subtract any preferred dividends, 
                  then divide the result by the sum of the weighted average number of shares outstanding and dilutive shares
                  Use the values calculted of yearly revenue, EBITDA, and adjusted diluted EPS to write the expert analysis for the company's financial performance for the next year.   
                  Here are some example guidance formats that you can use as a reference:
                  Example 1:
                  "Revenues of $15.7 - $16.3 billion. Non-GAAP operating income of $4.0-$4.5 billion. Adjusted EBITDA of $4.5 - $5.0 billion. Non-GAAP diluted EPS of $2.20 - $2.50",
                  Example 2:
                  the company expects net revenues between $520 million and $542 million, Cortrophin Gel Net Revenue in the range of $170 million - $180 million.
                  Example 3:
                  Royalty Pharma expects 2024 Portfolio Receipts to be between $2,600 million and $2,700 million. 2024 Portfolio Receipts guidance includes expected growth in royalty receipts of 5% to 9%.
                  The ideal length of the guidance is 1-3 sentences MAX and this is compulsory. Keep the information concise and to the point. The response should be based on the data provided. The response must also have quantitative values to support the guidance.
                  Ensure the quantitative values are realistic and accurately calculated based on typical industry standards and historical performance. 
                  And do not add any statements like " Thank you for feedback" or "We will take your feedback into consideration" in the guidance or anything that is like 
                  "We appreciate your feedback and are committed to providing accurate and reliable guidance for our shareholders. Thank you for bringing this to our attention." This is a report not a communication or chatbot response.
                  If you do find such statements in the guidance, please remove them.
                  '''
            })

        chat_history.append({"role": "user", "content": prompt_context})
        user_message = {
            "role": "user",
            "content": f"In a previous analysis from OpenAI, we have received the following guidance {existing_guidance}, but we have found some errors in the response and we would like to rectify the error in guidance with the following feedback and also maybe ask few questions {new_guidance_from_user}"
        }
        chat_history.append(user_message)

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=chat_history,
            max_tokens=3000,
        )
        current_company_report["guidance_chat"] = chat_history
        current_company_report["guidance"] = response['choices'][0]['message']['content']
        project["report"][version_index]["report"][company_index] = current_company_report

        chat_history.append({"role": "assistant", "content": response['choices'][0]['message']['content']})
        db.projects.update_one({"_id": ObjectId(project_id)}, {"$set": {"report": project['report']}})

        return chat_history
    except Exception as e:
        logging.error(f"Error extracting guidance: {str(e)}", exc_info=True)
        return e
