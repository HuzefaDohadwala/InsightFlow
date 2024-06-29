import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import csv
from datetime import datetime
from groq import Groq

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# MySQL configurations
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')

mysql = MySQL(app)

# Initialize Groq API client
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

def classify_review_groq(review):
    review_prompt = f"""Classify the following review into one of these categories strictly without any changes in the category as output and provide only the one-word category name from the given list:
    Technical issue
    Good user experience
    Bad user experience
    Good customer service
    Bad customer service
    Other

    Review: {review}
    """
    messages = [
        {
            "role": "system",
            "content": "Classify the review text based on the categories provided."
        },
        {
            "role": "user",
            "content": review_prompt
        }
    ]
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3-70b-8192"
    )
    return chat_completion.choices[0].message.content.strip()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account[0]
            session['username'] = account[1]
            return redirect(url_for('upload'))
        else:
            flash('Incorrect username/password!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE users SET password = %s WHERE username = %s', (new_password, username))
        mysql.connection.commit()
        flash('Password updated successfully!')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'loggedin' in session:
        if request.method == 'POST':
            file = request.files['file']
            if file.filename.endswith('.csv'):
                csv_file = file.read().decode('utf-8').splitlines()
                csv_reader = csv.DictReader(csv_file)
                required_columns = {'review', 'review_date', 'score'}
                
                if required_columns.issubset(csv_reader.fieldnames):
                    reviews = []
                    for row in csv_reader:
                        if row['review'] and row['review_date'] and row['score']:
                            review_date = datetime.strptime(row['review_date'], '%m/%d/%Y')
                            row['review_month'] = review_date.strftime('%B')
                            row['review_year'] = review_date.year
                            row['category'] = classify_review_groq(row['review'])
                            reviews.append(row)

                    cursor = mysql.connection.cursor()
                    for review in reviews:
                        cursor.execute(
                            'INSERT INTO reviews (review, review_month, review_year, review_category) VALUES (%s, %s, %s, %s)',
                            (review['review'], review['review_month'], review['review_year'], review['category'])
                        )
                    mysql.connection.commit()
                    flash(f'{len(reviews)} reviews uploaded successfully!')
                else:
                    flash('CSV file must contain review, review_date, and score columns')
            else:
                flash('Invalid file type. Please upload a CSV file.')
        return render_template('upload.html')
    return redirect(url_for('login'))

@app.route('/analysis')
def analysis():
    # Analysis logic here
    return render_template('analysis.html')

if __name__ == '__main__':
    app.run(debug=True)
