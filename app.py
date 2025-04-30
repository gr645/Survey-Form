from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash
import mysql.connector
import sys
from mysql.connector import Error

# Move these outside the try block
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

def log(message):
    print(message, file=sys.stderr, flush=True)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'gr',
    'raise_on_warnings': True,
    'port': 3306
}

# Initialize database connection
try:
    log("Connecting to database...")
    db = mysql.connector.connect(**DB_CONFIG)
    if not db.is_connected():
        raise Error("Failed to connect to database")
    log("Database connected successfully")
except Error as e:
    log(f"Database error: {e}")
    sys.exit(1)

@app.route('/')
def login_form():
    return render_template('form.html')  

@app.route('/login', methods=['POST'])
def login():
    name = request.form['logemail']
    password = request.form['logpass']

    cursor = db.cursor(dictionary=True)

    # Check in the 'users' table
    query_users = "SELECT * FROM users WHERE name = %s"
    cursor.execute(query_users, (name,))
    user = cursor.fetchone()

    if user and user['password'] == password:
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'user'
        flash('Welcome! You have successfully logged in.', 'success')
        return redirect(url_for('survey_panel'))

    # Check in the 'employee' table
    query_employee = "SELECT * FROM employee WHERE username = %s"
    cursor.execute(query_employee, (name,))
    employee = cursor.fetchone()

    if employee and employee['password'] == password:
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'employee'
        session['department'] = employee['department']
        flash('Welcome! You have successfully logged in.', 'success')
        return redirect(url_for('answer_questions'))

    flash('Invalid username or password.', 'error')
    return redirect(url_for('login_form'))


@app.route('/survey')
def survey_panel():
    if not session.get('logged_in') or session.get('role') != 'user':  # Check if the user is logged in and is a 'user'
        return redirect(url_for('login_form'))  # Redirect to login if not authenticated
    return render_template('survey.html')  # Render the survey creation page


@app.route('/submit_survey', methods=['POST'])
def submit_survey():
    if not session.get('logged_in') or session.get('role') != 'user':  # Ensure only users can submit surveys
        return redirect(url_for('login_form'))

    survey_data = request.json  # Get survey data from the frontend
    survey_title = survey_data['surveyTitle']
    department = survey_data['department']
    questions = survey_data['questions']

    # Insert survey and questions into the database
    cursor = db.cursor()
    cursor.execute('INSERT INTO surveys (title, department) VALUES (%s, %s)', (survey_title, department))
    survey_id = cursor.lastrowid  # Get the ID of the newly created survey

    for question in questions:
        cursor.execute(
            'INSERT INTO questions (survey_id, question_text, question_type, options) VALUES (%s, %s, %s, %s)',
            (survey_id, question['questionText'], question['questionType'], ','.join(question['options']))
        )

    db.commit()
    return jsonify({'message': 'Survey created successfully!'})


@app.route('/questions')
def answer_questions():
    if not session.get('logged_in') or session.get('role') != 'employee':
        flash('Please login as an employee to access this page.', 'error')
        return redirect(url_for('login_form'))

    department = session.get('department')
    cursor = db.cursor(dictionary=True)
    
    # Fetch surveys for the employee's department
    cursor.execute('''
        SELECT 
            s.id AS survey_id,
            s.title AS survey_title,
            q.id AS question_id,
            q.question_text,
            q.question_type,
            q.options
        FROM surveys s
        JOIN questions q ON s.id = q.survey_id
        WHERE s.department = %s
        ORDER BY s.id, q.id
    ''', (department,))
    
    results = cursor.fetchall()
    
    # Organize questions by survey
    surveys = {}
    for row in results:
        survey_id = row['survey_id']
        if survey_id not in surveys:
            surveys[survey_id] = {
                'title': row['survey_title'],
                'questions': []
            }
        surveys[survey_id]['questions'].append({
            'id': row['question_id'],
            'text': row['question_text'],
            'type': row['question_type'],
            'options': row['options'].split(',') if row['options'] else []
        })

    return render_template('questions.html', surveys=surveys)

@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    return redirect(url_for('login_form'))  # Redirect to login page

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            department = request.form['department']

            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO employee (username, email, password, department) VALUES (%s, %s, %s, %s)',
                (username, email, password, department)
            )
            db.commit()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login_form'))
        except mysql.connector.IntegrityError:
            flash('Email already exists. Please use a different email.', 'error')
            return redirect(url_for('signup'))
        except Exception as e:
            print(f"Database error: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')

if __name__ == '__main__':
    try:
        log("Starting Flask server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        log(f"Server error: {e}")
    finally:
        if 'db' in globals() and db.is_connected():
            db.close()
            log("Database connection closed")

