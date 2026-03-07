from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "farmer_ai_cybersecurity_key"  # Keep this secret

# MongoDB Connection
client = MongoClient("mongodb://localhost:27017/")
db = client['FarmerAI']
users_collection = db['users']


@app.route('/')
def index():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', name=session['user_name'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = users_collection.find_one({"email": email})

        if user and check_password_hash(user['password'], password):
            session['user_name'] = user['name']
            return redirect(url_for('index'))
        else:
            # Trigger: Redirect to register if login fails
            flash("Account not found or invalid credentials. Please register.")
            return redirect(url_for('register'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not users_collection.find_one({"email": email}):
            hashed_pw = generate_password_hash(password)
            users_collection.insert_one({"name": name, "email": email, "password": hashed_pw})
            return redirect(url_for('login'))
        flash("Email already exists!")
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)