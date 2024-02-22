import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from bson import ObjectId
from bson.json_util import dumps
import os
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

# Load environment variables from a .env file
load_dotenv()

# Set your OpenAI API key from the environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Initialize the Flask app and enable CORS
app = Flask(__name__)
CORS(app, origins="*")
app.config['CORS_HEADERS'] = 'Content-Type'

# Configure MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)
db = mongo.db

# Function to process a PDF file and extract text
def process_pdf(file_path):
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
        return text
    except Exception as e:
        logging.error(f"Error processing PDF: {str(e)}")
        return None

# Function to process a PDF file and store it in the 'uploads' folder
def process_pdf_and_store(file):
    try:
        uploads_folder = os.path.join(os.getcwd(), "uploads")
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)

        filename = secure_filename(file.filename)
        file_path = os.path.join(uploads_folder, filename)
        file.save(file_path)

        text = process_pdf(file_path)
        if text is not None:
            return filename
        else:
            os.remove(file_path)
            return None
    except Exception as e:
        logging.error(f"Error processing PDF and storing: {str(e)}")
        return None

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
def projects():
    if request.method == 'GET':
        projects = db.projects.find()
        projects = [{"_id": str(project["_id"]), **project} for project in projects]
        return dumps({"projects": projects}), 200

    elif request.method == 'POST':
        data = request.get_json()

        if 'name' not in data or 'description' not in data or 'filenames' not in data:
            return jsonify({"error": "Incomplete project information"}), 400

        name = data['name']
        description = data['description']
        filenames = data['filenames']

        project_data = {
            "name": name,
            "description": description,
            "filenames": filenames
        }

        db.projects.insert_one(project_data)

        return jsonify({"message": "Project created successfully"}), 201

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

# Function to get or create the vector store for text embeddings
def get_or_create_vector_store(chunks, store_name):
    embeddings_file_path = f"{store_name}.pkl"

    if os.path.exists(embeddings_file_path):
        with open(embeddings_file_path, "rb") as f:
            vector_store = pickle.load(f)
    else:
        embeddings = OpenAIEmbeddings()
        vector_store = FAISS.from_texts(chunks, embedding=embeddings)
        with open(embeddings_file_path, "wb") as f:
            pickle.dump(vector_store, f)

    return vector_store

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
            processed_text = process_pdf(pdf_path)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
