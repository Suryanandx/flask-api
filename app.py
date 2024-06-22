import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from bson import ObjectId
from bson.json_util import dumps
import os, sys
import pickle
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.llms import OpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.callbacks import get_openai_callback
import openai
from bs4 import BeautifulSoup
import requests
from pathlib import Path
import nltk
from PyPDF2 import PdfFileReader
import os
import argparse
import subprocess
import logging
import tabula
import json
from pdf2image import convert_from_path
import base64
import fitz
import pandas as pd 
from datetime import datetime
from sec_api import XbrlApi
from user_db.user_routes import init_routes

nltk.download('punkt')
from nltk.tokenize import sent_tokenize
import tiktoken
model = "gpt-4-turbo"
enc = tiktoken.encoding_for_model(model)
# Load environment variables from a .env file
load_dotenv()

# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
xbrlApi = XbrlApi(os.getenv("SEC_API_KEY"))

PORT = os.getenv("PORT")

# Initialize the Flask app and enable CORS
app = Flask(__name__)
CORS(app, origins="*")
app.config['CORS_HEADERS'] = 'Content-Type'

# Configure MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)
db = mongo.db
init_routes(app, db)
# Helper functions
from utils.parse_json_utils import scrape_and_get_reports
from utils.pdf_utils import process_pdf, process_pdf_and_store
from utils.text_utils import extract_text_and_save, get_or_create_vector_store
from utils.openai_utils import extract_json_from_images

# Route for the root endpoint
@app.route("/")
@cross_origin()
def helloWorld():
    return "Hello, API WORLD!"




@app.route('/scrape-and-query', methods=['POST'])
@cross_origin()
def scrape_and_query():
    data = request.get_json()
    urls = data.get('urls', [])
    user_query = data.get('query')

    if not urls or not user_query:
        return jsonify({"error": "URLs or query not provided"}), 400

    try:
        scraped_data = []

        for url in urls:
            # Scrape each website with a timeout of 60 seconds
            response = requests.get(url, timeout=60)
            response.raise_for_status()  # Check for HTTP errors

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                scraped_text = ' '.join([p.get_text() for p in soup.find_all('p')])
                scraped_data.append(scraped_text)

        # Join scraped data from all URLs into a single text
        all_scraped_data = ' '.join(scraped_data)

        # Query OpenAI's Davinci Chat Model
        openai.api_key = os.environ["OPENAI_API_KEY"]
        ai_response = openai.ChatCompletion.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a highly experienced Business Analyst and Financial Expert with a rich history of over 30 years in the field. Your expertise is firmly grounded in data-driven insights and comprehensive analysis. When presented with unsorted data, your primary objective is to meticulously filter out any extraneous or irrelevant components, including elements containing symbols like # and $. Furthermore, you excel at identifying and eliminating any HTML or XML tags and syntax within the data, streamlining it into a refined and meaningful form."},
                {"role": "user", "content": all_scraped_data},
                {"role": "assistant", "content": f"Question: {user_query}\nAnswer:"},
            ],
        )
        answer = ai_response['choices'][0]['message']['content']

        return jsonify({"response": answer})

    except requests.exceptions.RequestException as req_err:
        return jsonify({"error": f"Request error: {str(req_err)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Scraping error: {str(e)}"}), 500



# this is where the info comes from
@app.route('/scrape-and-query-pdf/<project_id>', methods=['POST'])
@cross_origin()
def scrape_and_query_pdf(project_id):
    print("calling scrape_and_query_pdf")
    data = request.get_json()
    urls = data.get('urls', [])
    user_query = data.get('query')
    project = db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404
    urls = project.get('filenames', [])

    if not urls or not user_query:
        return jsonify({"error": "URLs or query not provided"}), 400
    try:
        mainReport = extract_json_from_images(urls[0], user_query)
# remove loop for now
#       start_from = 1
        compReport = []
#       for index, item in enumerate(urls[start_from:], start_from):
#           current_comp_report =   extract_json_from_images(item, user_query)     
#           compReport.append(current_comp_report)



        db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"report_ai": {
            "main": mainReport,
            "comp": compReport,
            "growth_chart": [
                {
                "name": "Amneal",
                "value": 6.1
                },
                {
                "name": "Teva",
                "value": 6
                },
                {
                "name": "Eagle",
                "value": 8.7
                },
                {
                "name": "ANI",
                "value": 4.2
                }
            ],
            "stats": [
                {
                "name": "Amneal",
                "market_cap": 0.7,
                "net_leverage": 2.1,
                "sales": 4,
                "ebitda_margin": 2.2
                },
                {
                "name": "Teva",
                "market_cap": 1.7,
                "net_leverage": 4.2,
                "sales": 6,
                "ebitda_margin": 1.2
                },
                {
                "name": "Eagle",
                "market_cap": 0.9,
                "net_leverage": 3.1,
                "sales": 4.6,
                "ebitda_margin": 1.2
                },
                {
                "name": "ANI",
                "market_cap": 1.7,
                "net_leverage": 2.5,
                "sales": 6,
                "ebitda_margin": 2
                }
            ]
      
      
        }}}
        )
        return jsonify({"response": {
            "main": mainReport,
            "comp": compReport,
            "growth_chart": [
                {
                "name": "Amneal",
                "value": 6.1
                },
                {
                "name": "Teva",
                "value": 6
                },
                {
                "name": "Eagle",
                "value": 8.7
                },
                {
                "name": "ANI",
                "value": 4.2
                }
            ],
            "stats": [
                {
                "name": "Amneal",
                "market_cap": 0.7,
                "net_leverage": 2.1,
                "sales": 4,
                "ebitda_margin": 2.2
                },
                {
                "name": "Teva",
                "market_cap": 1.7,
                "net_leverage": 4.2,
                "sales": 6,
                "ebitda_margin": 1.2
                },
                {
                "name": "Eagle",
                "market_cap": 0.9,
                "net_leverage": 3.1,
                "sales": 4.6,
                "ebitda_margin": 1.2
                },
                {
                "name": "ANI",
                "market_cap": 1.7,
                "net_leverage": 2.5,
                "sales": 6,
                "ebitda_margin": 2
                }
            ]
      
        } })

    except requests.exceptions.RequestException as req_err:
        return jsonify({"error": f"Request error: {str(req_err)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Scraping error: {str(e)}"}), 500




@app.route('/scrape-and-query-pdf-to-text/<project_id>', methods=['POST'])
@cross_origin()
def scrape_and_query_pdf_save_to_txt(project_id):
    print("calling scrape_and_query_pdf")
    data = request.get_json()
    urls = data.get('urls', [])
    user_query = data.get('query')
    project = db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404
    urls = project.get('filenames', [])

    if not urls or not user_query:
        return jsonify({"error": "URLs or query not provided"}), 400
    try:
        mainReport = extract_text_and_save(urls[0])
        compReport = extract_text_and_save(urls[1])

        db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"report_txt": {
            "main": mainReport,
            "comp": compReport
        }}}
        )
        return jsonify({"response": {
            "main": mainReport,
            "comp": compReport
        } })

    except requests.exceptions.RequestException as req_err:
        return jsonify({"error": f"Request error: {str(req_err)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Scraping error: {str(e)}"}), 500




# Route to process and upload a file
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        filename = process_pdf_and_store(file)

        if filename:
            file_url = f"{request.url_root}uploads/{filename}"
            return jsonify({"file_url": file_url, "filename": filename}), 201
        else:
            return jsonify({"error": "Error processing PDF and storing"}), 500

    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500




# Route to get all projects or add a new project
@app.route('/projects', methods=['GET', 'POST'])
@cross_origin()
def projects():
    if request.method == 'GET':
        query_result = db.projects.find()
        projects = []
        for project in query_result:
            project_dict = {}
            for key, value in project.items():
                if key != "_id":
                    project_dict[key] = value
                else:
                    project_dict["_id"] = str(value)

            projects.append(project_dict)
            
        return jsonify({"projects": projects}), 200

    elif request.method == 'POST':
        try:
            data = request.get_json()
            if 'name' not in data or 'description' not in data or 'comps' not in data:
                return jsonify({"error": "Incomplete project information"}), 400

            project_name = data['name']
            project_description = data['description']
            comps = data['comps']
            report = data['report']

            # Comps will contain url field too
            url_array = []
            for comp in comps:
                url_array.append(comp['url'])

            scrapped_data = scrape_and_get_reports(url_array);
            print(scrapped_data)
# can move things here
            project_data = {
                "name": project_name,
                "description": project_description,
                "comps": comps,
                "scrapped_data": scrapped_data,
                "report": report
            }

            result = db.projects.insert_one(project_data);
            inserted_id = result.inserted_id

            inserted_document = db.projects.find_one({"_id": ObjectId(inserted_id)})
            inserted_document["_id"] = str(inserted_document["_id"])

            return jsonify({ "data" : inserted_document }), 201

        except Exception as e:
            return jsonify({"error": f"project adding  error: {str(e)}"}), 500




@app.route('/update_report/<id>', methods=['PUT'])
def update_report(id):
    try:
        data = request.get_json()
        new_report = data['report']

        if not new_report:
            return jsonify({"error": "Report field is required"}), 400

        # check if the id is valid
        if not ObjectId.is_valid(id):
            return jsonify({"error": "Invalid project ID"}), 400

        # check if document is there with the given id
        project = db.projects.find_one({"_id": ObjectId(id)})
        if not project:
            return jsonify({"error": f"Project with ID '{id}' not found"}), 404
        
        # update
        result = db.projects.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"report": new_report}}
        )

        # success or not?
        if result.modified_count == 0:
            return jsonify({"error": f"Project with ID '{id}' not updated"}), 500
        
        updated_document = db.projects.find_one({"_id": ObjectId(id)})
        updated_document["_id"] = str(updated_document["_id"])
        
        return jsonify(updated_document), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# Route to get a project by ID
@app.route('/projects/<project_id>', methods=['GET'])
def get_project_by_id(project_id):
    try:
        if not ObjectId.is_valid(project_id):
            return jsonify({"error": "Invalid project ID"}), 400

        project = db.projects.find_one({"_id": ObjectId(project_id)})


        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404

        project["_id"] = str(project["_id"])

        return jsonify({"project": project}), 200

    except Exception as e:
        logging.error(f"Error retrieving project by ID: {str(e)}")
        return jsonify({"error": f"Error retrieving project by ID: {str(e)}"}), 500




# Route to retrieve uploaded files
@app.route('/uploads/<filename>', methods=['GET'])
def get_uploaded_file(filename):
    return send_from_directory(os.path.join(os.getcwd(), "uploads"), filename)




# Chat API route
@app.route('/chat/<project_id>', methods=['POST'])
def chat(project_id):
    try:
        data = request.get_json()
        if 'query' not in data:
            return jsonify({"error": "Query not provided"}), 400

        query = data['query']

        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404

        filenames = project.get('filenames', [])
        text = ""
        for filename in filenames:
            pdf_path = os.path.join("uploads", filename)
            processed_text = process_pdf(pdf_path, "all")
            if processed_text is not None:
                text += processed_text

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        chunks = text_splitter.split_text(text=text)
        vector_store = get_or_create_vector_store(chunks, project_id)

        docs = vector_store.similarity_search(query=query, k=3)
        llm = OpenAI(temperature=0.7, model="gpt-3.5-turbo-instruct")
        chain = load_qa_chain(llm=llm, chain_type="stuff")

        with get_openai_callback() as cb:
            response = chain.run(input_documents=docs, question=query)

        chat_history = project.get('chat_history', [])
        chat_history.append({"user": query, "bot": response})

        db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"chat_history": chat_history}}
        )

        return jsonify({"response": response})

    except Exception as e:
        logging.error(f"Error processing chat request for project '{project_id}': {str(e)}")
        return jsonify({"error": f"Error processing chat request: {str(e)}"}), 500




# Chat API route
@app.route('/scrape-xbrl/<project_id>', methods=['POST'])
def scrap_xbrl(project_id):
    try:
        data = request.get_json()
        url_10k = data['xbrl']
        company_name = data['name']
        datapoint = data['datapoint']
        xbrl_json = xbrlApi.xbrl_to_json(htm_url=url_10k)
        return jsonify({"response": xbrl_json})

    except Exception as e:
        logging.error(f"Error processing chat request for project '{project_id}': {str(e)}")
        return jsonify({"error": f"Error processing chat request: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
