from flask import request
from flask import jsonify

def init_routes(app, db):
    @app.route('/register', methods=['POST'])
    def register():
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        user = {
            'username': username,
            'email': email,
            'password': password  # Store the password in plain text
        }

        # Insert the user into the 'users' collection
        db.users.insert_one(user)

        return jsonify({'message': 'registered successfully'}), 201

    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json()
        print(data)
        email = data.get('email')
        print(email)
        password = data.get('password')
        print(password)

        # Find the user in the 'users' collection
        user = db.users.find_one({'email': email})

        if user and user['password'] == password:  # Compare the passwords directly
            return jsonify({'message': 'logged in successfully'}), 200
        else:
            return jsonify({'message': 'invalid email or password'}), 401

    @app.route('/users', methods=['GET'])
    def get_users():
        users = db.users.find()

        user_list = []
        for user in users:
            if '_id' in user:
                del user['_id']
            user_list.append(user)

        return jsonify(user_list)

    @app.route('/clear', methods=['DELETE'])
    def clear_db():
        db.users.drop()
        return jsonify({'message': 'Database cleared'}), 200
    