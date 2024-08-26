from flask import Flask, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import pprint

app = Flask(__name__)

# Configure the MongoDB connection
app.config["MONGO_URI"] = "mongodb://localhost:27017/arizongpt"
mongo = PyMongo(app)


@app.route('/get_company_name/<id>', methods=['GET'])
def get_company_name(id):
    # Access the collection
    collection = mongo.db.projects
    # Find the document by _id
    project = collection.find_one({"_id": ObjectId(id)})

    if project:
        pprint.pprint(project)  # Print the project structure for debugging

        # Navigate to the company name in xbrl_json
        try:
            company_name = project['xbrl_json'][0]['name'][0]['value']
            return Response(company_name, mimetype='text/plain')
        except (KeyError, IndexError):
            return Response("Company name not found", mimetype='text/plain', status=404)
    else:
        return Response("Project not found", mimetype='text/plain', status=404)


if __name__ == '__main__':
    app.run(debug=True)
