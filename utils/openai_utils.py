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
    # pdf_path = os.path.join("uploads", filename)    
    
    # cmd = f"pdfgrep -Pn '^(?s:(?=.*consolidated results of operations)|(?=.*Consolidated Statements of Operations)|(?=.*Consolidated Statements of Cash Flows)|(?=.*CONSOLIDATED STATEMENTS OF CASH FLOWS)|(?=.*CONSOLIDATED STATEMENTS OF INCOME)|(?=.*Interest expenses and other bank charges)|(?=.*Depreciation and Amortization)|(?=.*CONSOLIDATED BALANCE SHEETS))' {pdf_path} | awk -F\":\" '$0~\":\"{{print $1}}' | tr '\n' ','"
    # print(cmd)
    # logging.info(cmd)
    # pages = subprocess.check_output(cmd, shell=True).decode("utf-8")
    # logging.info(f'count of pages {pages}')
    # print(pages)
    # pages_list = pages.split(",")
    # del pages_list[-1]
    # print(pages_list)
    # if not pages:
    #    logging.warning(f"No matching pages found in {pdf_path}")
    #    return
    # images = pdf_to_image(pdf_path, pages_list)
    # image_payloads = [ {
    #       "type": "image_url",
    #       "image_url": {
    #         "url": f"data:image/jpeg;base64,{t}"
    #       }
    #     } for t in zip(images)]

    # openai.api_key = os.environ["OPENAI_API_KEY"]
    # completion = openai.ChatCompletion.create(
    #     model=model,
    #     messages=[
    #         {"role": "user", "content": image_payloads},
    #         {"role": "user", "content": user_query},
    #     ]
    # )
    # print(completion.choices[0].message.content.strip() )
    # current_result = parse_json_garbage(completion.choices[0].message.content.strip() )
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
        model=model,
        messages=[
            {"role": "system", "content": "You are a highly experienced Business Analyst and Financial Expert with a rich history of over 30 years in the field. Your expertise is firmly grounded in data-driven insights and comprehensive analysis. When presented with unsorted data, your primary objective is to meticulously filter out any extraneous or irrelevant components, including elements containing symbols like # and $. Furthermore, you excel at identifying and eliminating any HTML or XML tags and syntax within the data, streamlining it into a refined and meaningful form."},
            {"role": "user", "content": text},
            {"role": "assistant", "content": f"Question: {user_query}\nAnswer:"},
        ]
    )
    print(completion.choices[0].message.content.strip() )
    current_result = parse_json_garbage(completion.choices[0].message.content.strip() )
    return current_result
