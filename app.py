from flask import Flask, request, jsonify, send_from_directory
import logging
import os
import time
import json
import subprocess
import openai
import requests
from bs4 import BeautifulSoup
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from flask_pymongo import PyMongo
from langchain.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sec_api import XbrlApi
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd

from user_db.user_routes import init_routes
from utils.web_scrapper import scrape_site


frontend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
import datetime as date


import tiktoken
model = "gpt-4-turbo"
enc = tiktoken.encoding_for_model(model)
# Load environment variables from a .env file
load_dotenv()

# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["PYTHON_ENV"] = os.getenv("PYTHON_ENV")
xbrlApi = XbrlApi(os.getenv("SEC_API_KEY"))

PORT = os.getenv("PORT")
PYTHON_ENV = os.getenv("PYTHON_ENV")

# Initialize the Flask app and enable CORS
app = Flask(__name__, static_folder='./public', static_url_path='/')
CORS(app, origins="*")
app.config['CORS_HEADERS'] = 'Content-Type'

# Configure MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)
db = mongo.db
init_routes(app, db)
# Helper functions
from utils.parse_json_utils import scrape_and_get_reports, xbrl_to_json
from utils.pdf_utils import process_pdf, process_pdf_and_store
from utils.text_utils import extract_text_and_save, get_or_create_vector_store
from utils.openai_utils import append_guidance_analysis, extract_json_from_images, analysis_from_html, append_note_analysis


# Route for the root endpoint
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.errorhandler(404)
def catch_all(path):
    return app.send_static_file('index.html')


@app.route('/api/scrape-and-query', methods=['POST'])
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
            current_scrapped_text = scrape_site(url)
            scraped_data.append(current_scrapped_text)

        # Join scraped data from all URLs into a single text
        all_scraped_data = ' '.join(scraped_data)

        # answer = analysis_from_html(all_scraped_data, user_query)

        return jsonify({"response": all_scraped_data})

    except requests.exceptions.RequestException as req_err:
        return jsonify({"error": f"Request error: {str(req_err)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Scraping error: {str(e)}"}), 500






# Route to process and upload a file
@app.route('/api/upload', methods=['POST'])
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
@app.route('/api/projects', methods=['GET', 'POST'])
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

            # Comps will contain url field too
            url_array = []
            for comp in comps:
                url_array.append(comp['url'])

            # scrapped_data = scrape_and_get_reports(url_array);
            print("url array", url_array)
            scrapped_data = xbrl_to_json(url_array)
            project_data = {
                "name": project_name,
                "description": project_description,
                "comps": comps,
                "xbrl_json": scrapped_data
            }

            result = db.projects.insert_one(project_data);
            inserted_id = result.inserted_id

            inserted_document = db.projects.find_one({"_id": ObjectId(inserted_id)})
            inserted_document["_id"] = str(inserted_document["_id"])

            return jsonify({ "data" : inserted_document }), 201

        except Exception as e:
            return jsonify({"error": f"project adding  error: {str(e)}"}), 500




@app.route('/api/update_report/<id>', methods=['PUT'])
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
@app.route('/api/projects/<project_id>', methods=['GET'])
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


@app.route('/api/projects/<project_id>/extract', methods=['GET'])
def get_project_by_id_and_extract(project_id):
    try:
        if not ObjectId.is_valid(project_id):
            return jsonify({"error": "Invalid project ID"}), 400

        project = db.projects.find_one({"_id": ObjectId(project_id)})
        scrapped_data = scrape_and_get_reports(project['xbrl_json'], project_id);
        new_report = {
            "timestamp": time.time(),
            "report": scrapped_data
        }
        project['report'].append(new_report);
        db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"report": project['report']}}
        )
        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404

        project["_id"] = str(project["_id"])

        return jsonify({"project": project}), 200

    except Exception as e:
        print(e)
        logging.error(f"Error retrieving project by ID: {str(e)}")
        return jsonify({"error": f"Error retrieving project by ID: {str(e)}"}), 500




@app.route('/api/projects/<project_id>/append_guidance', methods=['POST'])
@cross_origin()
def get_project_by_id_and_append(project_id):
    try:
        if not ObjectId.is_valid(project_id):
            return jsonify({"error": "Invalid project ID"}), 400

        project = db.projects.find_one({"_id": ObjectId(project_id)})

        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404
        
        request_json = request.get_json()
        company_index = request_json['company_index']
        new_guidance_from_user = request_json['new_guidance']
        existing_guidance = project['report'][company_index]['guidance']
        reponse_from_append = append_guidance_analysis(project, company_index, existing_guidance, new_guidance_from_user, project_id)
        new_report = project['report']
        new_report[company_index]['guidance'] = reponse_from_append



        db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"report": new_report}}
        )

        project["_id"] = str(project["_id"])

        return jsonify({"project": project}), 200

    except Exception as e:
        print(e)
        logging.error(f"Error retrieving project by ID: {str(e)}")
        return jsonify({"error": f"Error retrieving project by ID: {str(e)}"}), 500
    

    
@app.route('/api/projects/<project_id>/append_note', methods=['POST'])
@cross_origin()
def get_project_by_id_and_append_note(project_id):
    try:
        if not ObjectId.is_valid(project_id):
            return jsonify({"error": "Invalid project ID"}), 400
        
        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404
        
        request_json = request.get_json()
        company_index = request_json['company_index']
        new_note_from_user = request_json['new_note']
        existing_note = project['report'][company_index]['note']
        reponse_from_append = append_note_analysis(project, company_index, existing_note, new_note_from_user, project_id)
        new_report = project['report']
        new_report[company_index]['note'] = reponse_from_append

        db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"report": new_report}}
        )

        project["_id"] = str(project["_id"])

        return jsonify({"project": project}), 200
    
    except Exception as e:
        print(e)
        logging.error(f"Error retrieving project by ID: {str(e)}")
        return jsonify({"error": f"Error retrieving project by ID: {str(e)}"}), 500
        


# Route to retrieve uploaded files
@app.route('/api/uploads/<filename>', methods=['GET'])
def get_uploaded_file(filename):
    return send_from_directory(os.path.join(os.getcwd(), "uploads"), filename)

@app.route('/api/projects/report_changes', methods=['POST'])
def guidance_change():
    try:
        data = request.get_json()
        project_id = data['project_id']
        email = data['email']
        item = data['item'] # this varaible is used to identify the item that was changed
        old_value = data['old_value']
        new_value = data['new_new value']
        companyName = data['companyName']  
        timestamp = date.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.report_changes.insert_one({
        "project_id": project_id,
        "email": email,
        "companyName": companyName,
        "item": item,
        "old_value": old_value,
        "new_value": new_value,
        "timestamp": timestamp
        })
        
        return jsonify({"message": "Report change recorded successfully"}), 201

    except Exception as e:
        return jsonify({"error": f"Error recording report change: {str(e)}"}), 500


@app.route('/api/projects/<project_id>/get_report_changes', methods=['POST'])     
def get_report_changes(project_id):
    try:
        if not ObjectId.is_valid(project_id):
            return jsonify({"error": "Invalid project ID"}), 400
        
        changes = db.report_changes.find({"project_id": project_id})
        changes_list = []
        for change in changes:
            change["_id"] = str(change["_id"])
            changes_list.append(change)

        return jsonify({"changes": changes_list}), 200

    except Exception as e:
        return jsonify({"error": f"Error retrieving report changes: {str(e)}"}), 500



# Chat API route
@app.route('/api/chat/<project_id>', methods=['POST'])
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
        llm = OpenAI(temperature=0.7, model="gpt-4-turbo")
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


# Function to extract net revenue from XBRL file
def extract_net_revenue_from_xbrl(xbrl_file_path):
    output_json_path = 'sec_api_response.json'
    # Define the command to run Arelle in command line mode
    command = [
        'python', '-m', 'arelle.CntlrCmdLine',
        '--file', xbrl_file_path,
        '--facts', output_json_path
    ]

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(f"Conversion successful, JSON saved to {output_json_path}")
    # Fetch the XBRL file content
    response = requests.get(output_json_path)
    response.raise_for_status()

    return response.content




# Chat API route
@app.route('/api/scrape-xbrl/<project_id>', methods=['POST'])
def scrap_xbrl(project_id):
    try:
        data = request.get_json()
        url_10k = data['xbrl']
        net_revenue_df = extract_net_revenue_from_xbrl(url_10k)
        return net_revenue_df

    except Exception as e:
        logging.error(f"Error processing chat request for project '{project_id}': {str(e)}", exc_info=True)
        return jsonify({"error": f"Error processing chat request: {str(e)}"}), 500


'''@app.route('/test_refine_text', methods=['GET'])
def test_refine_text():
    text = "https://investors.amneal.com/news/press-releases/press-release-details/2024/Amneal-Reports-First-Quarter-2024-Financial-Results/default.aspx"
    try:
        refined_text = scrape_site(text)
        print(refined_text)
        return jsonify({'refined_text': refined_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500'''



@app.route('/api/guidance_chat/<project_id>', methods=['POST'])
def test_guidance(project_id):
    from utils.guidance_chat import append_guidance_analysis_chat
    try:
        data = request.get_json()
        new_guidance_from_user = data.get('new_guidance_from_user')
        existing_guidance = data.get('existing_guidance')
        company_index = data.get('company_index')
        version_index = data.get('version_index')
        project_id = data.get('project_id')

        
        if not new_guidance_from_user or not project_id or not existing_guidance or not company_index:
            return jsonify({"error": "Missing required fields"}), 400

        
        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404

        
        if 'report' not in project or len(project['report']) <= company_index:
            return jsonify({"error": "Company report not found"}), 404

        api_output = append_guidance_analysis_chat(db, new_guidance_from_user, existing_guidance, project_id, company_index, version_index, project)

        return jsonify({"message": "Guidance analysis chat appended successfully", "chat_history": api_output}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)

@app.route('/api/note_chat/<project_id>', methods=['POST'])
def test_guidance(project_id):
    from utils.note_chat import append_note_chat
    try:
        data = request.get_json()
        new_note_from_user = data.get('new_note_from_user')
        existing_note = data.get('existing_note')
        company_index = data.get('company_index')
        version_index = data.get('version_index')
        project_id = data.get('project_id')

        
        if not new_note_from_user or not project_id or not existing_note or not company_index:
            return jsonify({"error": "Missing required fields"}), 400

        
        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return jsonify({"error": f"Project with ID '{project_id}' not found"}), 404

        
        if 'report' not in project or len(project['report']) <= company_index:
            return jsonify({"error": "Company report not found"}), 404

        api_output = append_note_chat(db, new_note_from_user, existing_note, project_id, company_index, version_index, project)

        return jsonify({"message": "expert analysis chat appended successfully", "chat_history": api_output}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)