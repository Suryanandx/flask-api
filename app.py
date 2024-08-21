import logging
import os
import time

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
from sec_api import XbrlApi
from werkzeug.utils import secure_filename

from user_db.user_routes import init_routes

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


# Route for the root endpoint
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.errorhandler(404)
def catch_all(path):
    return app.send_static_file('index.html')


# Route to process and upload a file
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']

        uploads_folder = os.path.join(os.getcwd(), "uploads")
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)

        filename = secure_filename(file.filename)
        file_path = os.path.join(uploads_folder, filename)
        file.save(file_path)

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400


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
            uploads_folder = os.path.join(os.getcwd(), "uploads")
            # Comps will contain url field too
            url_array = []
            for comp in comps:
                file_path = os.path.join(uploads_folder, comp['files'][0]["filename"])
                url_array.append(file_path)

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
        if 'report' not in project:
            project['report'] = []

        # Append the new report to the list
        project['report'].append(new_report)
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
        logging.error(f"Error retrieving project by ID: {str(e)}", exc_info=True)
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







@app.route('/api/test_guidance', methods=['POST'])
def test_guidance():
    from utils.guidance_chat import append_guidance_analysis_chat
    try:
        data = request.get_json()
        new_guidance_from_user = data.get('new_guidance_from_user')
        existing_guidance = data.get('existing_guidance')
        company_index = data.get('company_index')
        version_index = data.get('version_index')
        project_id = data.get('project_id')

        
        if not new_guidance_from_user or not project_id or not existing_guidance or not company_index >= 0:
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




@app.route('/api/note_chat', methods=['POST'])
def test_note():
    from utils.note_chat import append_note_chat
    try:
        data = request.get_json()
        new_note_from_user = data.get('new_note_from_user')
        existing_note = data.get('existing_note')
        company_index = data.get('company_index')
        version_index = data.get('version_index')
        project_id = data.get('project_id')

        if not new_note_from_user or not project_id or not existing_note or not company_index >= 0:
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