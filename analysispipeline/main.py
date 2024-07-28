import os
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session , send_file ,Response, stream_with_context
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import csv
from datetime import datetime
from groq import Groq
import MySQLdb.cursors
from fpdf import FPDF
import time

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
print('MySQL connected successfully')

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

def fetch_reviews(month, year , category , product):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "SELECT review FROM reviews WHERE review_month = %s AND review_year=%s AND review_category = %s AND product_name = %s "
    cursor.execute(query, (month, year ,category , product))
    reviews = cursor.fetchall()
    cursor.close()
    return [review['review'] for review in reviews]

def analyze_batch(reviews_batch):
    messages = [
        {"role": "system", 
         "content": """
                You are a data analyst specialist. Your task is to analyze the main themes and underlying factors in the reviews and provide:
                For each prompt:

                Identify the primary theme or sentiment in the reviews.
                Identify the root cause or driving factor behind this theme/sentiment.

                Respond in a formal tone and only provide the list of primary themes/sentiments and their root causes/driving factors. No extra information is required.
            """},
        {"role": "user", "content": reviews_batch}
    ]
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3-70b-8192"
    )
    return chat_completion.choices[0].message.content.strip()

def generate_report(final_report,product):
    
    messages = [
        {"role": "system", 
         "content": """
                You are an expert data analyst tasked with creating a comprehensive report based on review analysis. Your report should be formal, structured, and include the following elements:

                Title: "Data Analysis Report:<PRODUCT_NAME> "
                Executive Summary

                Briefly outline the primary theme/sentiment and key findings


                Introduction

                Purpose of the analysis
                Overview of the data source and methodology


                Primary Theme/Sentiment Analysis

                Detailed description of the primary theme or sentiment identified
                Supporting data or quotes from reviews


                Root Causes/Driving Factors

                List and explain all possible root causes or driving factors
                Provide evidence or examples for each


                Key Performance Indicators (KPIs)

                Identify and explain relevant KPIs related to the primary theme
                Present data visualizations if applicable


                Possible Solutions

                Propose potential solutions or improvements addressing the root causes
                Discuss the feasibility and potential impact of each solution


                Actionable Insights

                Provide specific, data-driven recommendations
                Prioritize actions based on potential impact and ease of implementation


                Additional Observations

                Include any other relevant findings or patterns observed in the data


                Conclusion

                Summarize the main points of the report
                Reiterate the most critical insights and recommendations


                Appendix (if necessary)

                Include any supplementary data, charts, or detailed analyses """},
        {"role": "user", "content":f'PRODUCT NAME IS {product}' + final_report}
    ]
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3-70b-8192"
    )
    
    return chat_completion.choices[0].message.content.strip()

def create_pdf_report(analysis_results, file_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for result in analysis_results:
        pdf.multi_cell(0, 10, result)
    print("PDF report created")
    pdf.output(file_path)


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
        cursor.close()
        if account:
            print("Login successful, redirecting to upload page.")
            session['loggedin'] = True
            session['id'] = account[0]
            session['username'] = account[1]
            return redirect(url_for('upload'))
        else:
            flash('Incorrect username/password!')
            print("Login failed, incorrect username/password.")
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

@app.route('/progress')
def progress_stream():
    def generate():
        global progress
        while progress < 100:
            yield f"data:{progress}\n\n"
            time.sleep(0.1)  # Adjust sleep duration as needed
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global progress
    progress = 0
    print("Session in upload route: ", session)
    if 'loggedin' in session:
        if request.method == 'POST':
            print("POST request received")
            if 'file' not in request.files:
                print("No file part in the request")
                return jsonify({'progress': 0, 'error': 'No file part'})
            file = request.files['file']
            if file.filename == '':
                print("No file selected")
                return jsonify({'progress': 0, 'error': 'No file selected'})
            if file and file.filename.endswith('.csv'):
                print(f"Processing file: {file.filename}")
                try:
                    csv_file = file.read().decode('utf-8').splitlines()
                    csv_reader = csv.DictReader(csv_file)
                    required_columns = {'review', 'review_date', 'score' , 'product_name' }
                    
                    if required_columns.issubset(csv_reader.fieldnames):
                        print("Required columns found")
                        total_reviews = sum(1 for row in csv_reader if row['review'] and row['review_date'] and row['score'] and row['product_name'])
                        print(f"Total reviews: {total_reviews}")
                        file.seek(0)  # Reset file pointer to the beginning
                        csv_file = file.read().decode('utf-8').splitlines()
                        csv_reader = csv.DictReader(csv_file)
                        reviews = []
                        for i, row in enumerate(csv_reader):
                            print(f"Processing row {i+1}")
                            if row['review'] and row['review_date'] and row['score']:
                                try:
                                    print(f"Review date: {row['review_date']}")
                                    try:
                                        review_date = datetime.strptime(row['review_date'], '%d-%b-%y')
                                    except ValueError:
                                        review_date = datetime.strptime(row['review_date'], '%d/%m/%y')
                                    print(f"Parsed review date: {review_date}")
                                    row['review_month'] = review_date.strftime('%B')
                                    row['review_year'] = review_date.year
                                    print("Classifying review...")
                                    row['category'] = classify_review_groq(row['review'])
                                    print(f"Review classified as: {row['category']}")
                                    reviews.append(row)
                                    cursor = mysql.connection.cursor()
                                    cursor.execute(
                                        'INSERT INTO reviews (review, review_month, review_year, score, product_name,review_category) VALUES (%s, %s, %s, %s, %s, %s)',
                                        (row['review'], row['review_month'], row['review_year'], row['score'], row['product_name'], row['category'])
                                    )
                                    mysql.connection.commit()
                                    progress = int((i + 1) / total_reviews * 100)
                                    print(f'Progress: {progress}%')
                                    time.sleep(0.01)
                                except Exception as e:
                                    print(f"Error processing row {i+1}: {str(e)}")
                            else:
                                print(f"Skipping row {i+1} due to missing data")
                        print(f"Processed {len(reviews)} reviews")
                        progress = 100
                        return jsonify({'progress': 100, 'message': f'{len(reviews)} reviews uploaded successfully!'})
                    else:
                        print("Missing required columns")
                        return jsonify({'progress': 0, 'error': 'CSV file must contain review, review_date, and score columns'})
                except Exception as e:
                    print(f"Error processing file: {str(e)}")
                    return jsonify({'progress': 0, 'error': f'Error processing file: {str(e)}'})
            else:
                print("Invalid file type")
                return jsonify({'progress': 0, 'error': 'Invalid file type. Please upload a CSV file.'})
        return render_template('upload.html')
    return redirect(url_for('login'))

@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    products = get_unique_products()
    if request.method == 'POST':
        if 'analyze' in request.form:
            month = request.form['month']
            year = request.form['year']
            category = request.form['category']
            product = request.form['product']

            reviews = fetch_reviews(month, year, category , product)
            analysis_results = []
            print(analysis_results)
            
            for i in range(0, len(reviews), 100):
                batch = ' '.join(reviews[i:i + 100])
                analysis_result = analyze_batch(batch)
                analysis_results.append(analysis_result)
                print(analysis_results)

            join_report = '\n\n'.join(analysis_results)
            final_report=generate_report(join_report,product)
            # print(final_report)

            # Save final report to session for further queries
            session['final_report'] = final_report

            # Ensure the 'static' directory exists
            pdf_path = os.path.join('static', 'analysis_report.pdf')
            create_pdf_report([final_report], pdf_path)
            print(f"PDF report saved to: {pdf_path}")
            
            session['pdf_path'] = pdf_path  # Store pdf_path in session
            
            return render_template('analysis.html', summary=final_report, pdf_path=pdf_path)


        elif 'ask' in request.form:
            question = request.form['question']
            history = session.get('history', [])
            final_report = session.get('final_report')

            context = f"Final Report:\n{final_report}\n\nHistory:\n" + '\n'.join(history) + f"\n\nQuestion:\n{question}"
            messages = [
                {"role": "system", "content": "Provide detailed analysis and answer the user's questions based on the final report and history."},
                {"role": "user", "content": context}
            ]
            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama3-70b-8192"
            )
            answer = chat_completion.choices[0].message.content.strip()

            history.append(f"Q: {question}\nA: {answer}")
            session['history'] = history

            pdf_path = session.get('pdf_path', '')  # Get pdf_path from session, default to empty string if not found

            return render_template('analysis.html', summary=final_report, answer=answer, history=history, pdf_path=session['pdf_path'])

    return render_template('analysis.html',products=products)

def get_unique_products():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "SELECT DISTINCT product_name FROM reviews"
    cursor.execute(query)
    products = cursor.fetchall()
    cursor.close()
    return [product['product_name'] for product in products]



@app.route('/download_report')
def download_report():
    pdf_path = session.get('pdf_path')
    if pdf_path and os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    flash('Report not found.')
    return redirect(url_for('analysis'))


@app.route('/manage_db', methods=['GET', 'POST'])
def manage_db():
    products = get_unique_products()
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        month = request.form['month']
        year = request.form['year']
        category = request.form['category']
        product = request.form['product']
        action = request.form['action']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        if action == 'delete':
            query = "DELETE FROM reviews WHERE review_month = %s AND review_year = %s AND review_category = %s AND product_name = %s"
            cursor.execute(query, (month, year, category, product))
            mysql.connection.commit()
            message = f"Reviews deleted successfully for {month} {year}, category: {category}, product: {product}"
            return render_template('manage_db.html', message=message)

        elif action == 'display':
            query = "SELECT * FROM reviews WHERE review_month = %s AND review_year = %s AND review_category = %s AND product_name = %s"
            cursor.execute(query, (month, year, category, product))
            reviews = cursor.fetchall()
            return render_template('manage_db.html', reviews=reviews)

    return render_template('manage_db.html', products=products)

if __name__ == '__main__':
    app.run(debug=True)
