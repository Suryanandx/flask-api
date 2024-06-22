import os
import logging
import subprocess
import openai

from utils.pdf_utils import process_pdf, pdf_to_image



def parse_json_garbage(s):
    s = s[next(idx for idx, c in enumerate(s) if c in "{["):]
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        return json.loads(s[:e.pos])

def extract_json_from_images(filename, user_query):
     pdf_path = os.path.join("uploads", filename)    
    
     cmd = f"pdfgrep -Pn '^(?s:(?=.*consolidated results of operations)|(?=.*Consolidated Statements of Operations)|(?=.*Consolidated Statements of Cash Flows)|(?=.*CONSOLIDATED STATEMENTS OF CASH FLOWS)|(?=.*CONSOLIDATED STATEMENTS OF INCOME)|(?=.*Interest expenses and other bank charges)|(?=.*Depreciation and Amortization)|(?=.*CONSOLIDATED BALANCE SHEETS))' {pdf_path} | awk -F\":\" '$0~\":\"{{print $1}}' | tr '\n' ','"
     print(cmd)
     logging.info(cmd)
     pages = subprocess.check_output(cmd, shell=True).decode("utf-8")
     logging.info(f'count of pages {pages}')
     print(pages)
     pages_list = pages.split(",")
     del pages_list[-1]
     print(pages_list)
     if not pages:
        logging.warning(f"No matching pages found in {pdf_path}")
        return
     images = pdf_to_image(pdf_path, pages_list)
     image_payloads = [ {
           "type": "image_url",
           "image_url": {
             "url": f"data:image/jpeg;base64,{t}"
           }
         } for t in zip(images)]

     openai.api_key = os.environ["OPENAI_API_KEY"]
     completion = openai.ChatCompletion.create(
         model=model,
         messages=[
             {"role": "user", "content": image_payloads},
             {"role": "user", "content": user_query},
         ]
     )
     print(completion.choices[0].message.content.strip() )
     current_result = parse_json_garbage(completion.choices[0].message.content.strip() )
     return {"image": "Sample"}

def extract_json(filename, user_query):
    text = ""
    pdf_path = os.path.join("uploads", filename)
    
    cmd = f"pdfgrep -Pn '^(?s:(?=.*consolidated results of operations)|(?=.*Consolidated Statements of Cash Flows)|(?=.*CONSOLIDATED STATEMENTS))' {pdf_path} | awk -F\":\" '$0~\":\"{{print $1}}' | tr '\n' ','"
    print(cmd)
    logging.info(cmd)
    pages = subprocess.check_output(cmd, shell=True).decode("utf-8")
    logging.info(f'count of pages {pages}')
    if not pages:
       logging.warning(f"No matching pages found in {pdf_path}")
       return
    processed_text = process_pdf(pdf_path, pages)
    if processed_text is not None:
        text += processed_text
    openai.api_key = os.environ["OPENAI_API_KEY"]
    print(text)
    completion = openai.ChatCompletion.create(
        model= model,
        messages=[
            {"role": "system", "content": "You are a highly experienced Business Analyst and Financial Expert with a rich history of over 30 years in the field. Your expertise is firmly grounded in data-driven insights and comprehensive analysis. When presented with unsorted data, your primary objective is to meticulously filter out any extraneous or irrelevant components, including elements containing symbols like # and $. Furthermore, you excel at identifying and eliminating any HTML or XML tags and syntax within the data, streamlining it into a refined and meaningful form."},
            {"role": "user", "content": text},
            {"role": "assistant", "content": f"Question: {user_query}\nAnswer:"},
        ]
    )
    print(completion.choices[0].message.content.strip() )
    current_result = parse_json_garbage(completion.choices[0].message.content.strip() )
    return current_result

def generate_guidance(data): #this is the function that will generate the guidance for the company
    openai.api_key = os.environ["OPENAI_API_KEY"]
    prompt = f"The company {data['name']} has the following financial data:\n"
    for key, value in data.items():
        if key != 'name':
            prompt += f"{key}: {value}\n"
    prompt += '''You are a highly experienced Business Analyst and Financial Expert with a rich history of over 30 years in the field. Based only from this data, what is the guidance for the company's financial performance for the next year? 
    Here are some example guidance formats that you can use as a reference:
    Example 1:
    "Revenues of $15.7 - $16.3 billion. Non-GAAP operating income of $4.0-$4.5 billion. Adjusted EBITDA of $4.5 - $5.0 billion. Non-GAAP diluted EPS of $2.20 - $2.50",
    Example 2:
    the company expects net revenues between $520 million and $542 million, Cortrophin Gel Net Revenue in the range of $170 million - $180 million.
    Example 3:
    Royalty Pharma expects 2024 Portfolio Receipts to be between $2,600 million and $2,700 million. 2024 Portfolio Receipts guidance includes expected growth in royalty receipts of 5% to 9%.
    The ideal length of the guidance is 1-3 sentences MAX and this is compulsory. Keep the information concise and to the point. The response should be based on the data provided. The response must also have quantitative values to support the guidance.
    Ensure the quantitative values are realistic and accurately calculated based on typical industry standards and historical performance.
     '''
    response = openai.Completion.create(
      model ="gpt-3.5-turbo-instruct",
      prompt=prompt,
      max_tokens=300,
      temperature=0,
      n = 1
    )
    
    return response.choices[0].text.strip(),  

'''if __name__ == "__main__":
    data = {'Operating Income': [{'year': '2023', 'value': '204374000'}, {'year': '2022', 'value': '-94928000'}, {'year': '2021', 'value': '152716000'}], 'Profit Loss': [{'year': '2023', 'value': '-48722000'}, {'year': '2022', 'value': '-254789000'}, {'year': '2021', 'value': '20170000'}], 'Net income': [{'year': '2023', 'value': '-83993000'}, {'year': '2022', 'value': '-129986000'}, {'year': '2021', 'value': '10624000'}], 'interest expense': [{'year': '2023', 'value': '-210629000'}, {'year': '2022', 'value': '-158377000'}, {'year': '2021', 'value': '-136325000'}], 'Income Tax': [{'year': '2023', 'value': '-2496000'}, {'year': '2022', 'value': '-12649000'}, {'year': '2021', 'value': '-15558000'}], 'Depreciation & Amortization': [{'year': '2023', 'value': '229400000'}, {'year': '2022', 'value': '240175000'}, {'year': '2021', 'value': '233406000'}], 'Net Revenue': [{'year': '2023', 'value': '2393607000'}, {'year': '2022', 'value': '2212304000'}, {'year': '2021', 'value': '2093669000'}], 'name': 'Amneal Pharmaceuticals, Inc.', 'ebitda': [{'year': '2023', 'value': '433774000'}, {'year': '2022', 'value': '145247000'}, {'year': '2021', 'value': '386122000'}], 'annual revenue growth': [{'year': '2023', 'value': '8.195211869616472 %'}, {'year': '2022', 'value': '5.666368466075583 %'}], 'ebitda growth': [{'year': '2023', 'value': '198.64575516189663 %'}, {'year': '2022', 'value': '-62.38313279222629 %'}], 'year': '2023'}
    guidance_tuple = generate_guidance(data)
    cleaned_guidance = tuple(s.replace("\\n", "\n") for s in guidance_tuple)
    for item in cleaned_guidance:
        print(item)
    print(guidance_tuple)'''

