import mysql.connector
from flask import Flask, request, redirect, url_for, session, render_template, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



app = Flask(__name__)
app.secret_key = "your_secret_key_here"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "SYSARCH",
    "port": 3306
}

#Index route
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'login' in request.form:
            return redirect(url_for('login_dashboard'))
        elif 'register' in request.form:
            return redirect(url_for('register_user'))

    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_dashboard():
    # 🔹 Redirect users if they are already logged in
    if 'role' in session and session['role'] in ['admin', 'staff', 'student']:
        return redirect(url_for(f"{session['role']}_dashboard")) 

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # 🔹 Dictionary mapping tables to roles
        databases = {
            "admins": "admin",
            "staffs": "staff",
            "students": "student"
        }

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)

            # 🔹 Check in each table
            for table_name, role in databases.items():
                query = f"SELECT id, password, firstname, lastname FROM {table_name} WHERE username=%s"
                cursor.execute(query, (username,))
                user = cursor.fetchone()

                if user:
                    stored_password = user['password']
                    if check_password_hash(stored_password, password):
                        # 🔹 Clear the session before setting new user data
                        session.clear()
                        session.update({
                            'user_id': user['id'],  # Save user ID for reference
                            'username': username,
                            'firstname': user['firstname'],
                            'lastname': user['lastname'],
                            'role': role
                        })
                        flash(f"Welcome, {user['firstname']}!", "success")
                        return redirect(url_for(f"{role}_dashboard"))  # Redirect based on role

            # 🔹 If no match found
            error = "Invalid username or password."
            flash(error, 'danger')

        except mysql.connector.Error as e:
            flash(f"Database error: {e}", 'danger')

        finally:
            cursor.close()
            conn.close()

    return render_template('login.html', error=error)

@app.route('/registeruser')
def register_user():
    return render_template("registeruser.html")  # Render registration page

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    database_map = {
        "admin": "admins",
        "staff": "staffs",
        "student": "students"
    }

    if role not in database_map:
        flash("Invalid role.", 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        midname = request.form.get('midname', '')
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match.", 'danger')
            return redirect(url_for('register', role=role))

        hashed_password = generate_password_hash(password)
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        table_name = database_map[role]
        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # 🔹 Create query dynamically based on role
            if role == "student":
                course = request.form.get('course', '')
                yearlevel = request.form.get('yearlevel', '')
                remaining_sessions = 5  # Students start with 5 sessions
                
                query = f'''
                    INSERT INTO {table_name} 
                    (username, password, firstname, lastname, midname, course, yearlevel, email, registration_date, remaining_sessions) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                values = (username, hashed_password, firstname, lastname, midname, 
                          course, yearlevel, email, registration_date, remaining_sessions)
            
            else:  # 🔹 Admins & Staff (no course or yearlevel)
                query = f'''
                    INSERT INTO {table_name} 
                    (username, password, firstname, lastname, midname, email, registration_date) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                '''
                values = (username, hashed_password, firstname, lastname, midname, email, registration_date)

            cursor.execute(query, values)
            conn.commit()

            new_id = cursor.lastrowid  # Auto-generated ID

            flash(f"Successfully registered as {role}! Your ID is {new_id}.", 'success')
            return redirect(url_for('login_dashboard'))

        except mysql.connector.IntegrityError as e:
            if "Duplicate entry" in str(e):
                flash("Email already exists. Please use a different email.", 'danger')
            else:
                flash("An error occurred. Please try again.", 'danger')
            return redirect(url_for('register', role=role))

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template(f'register_{role}.html')  # Render role-specific form





#MGA DASHBOARDS

#ADMIN
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login_dashboard'))

    students = []

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Fetch students
        cursor.execute("SELECT id, username, firstname, midname, lastname, email, registration_date FROM students")
        students = cursor.fetchall()

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return render_template('error.html', message="An error occurred while fetching data.")

    finally:
        cursor.close()
        conn.close()

    return render_template('admin_dashboard.html', students=students)

@app.route('/get_students', methods=['GET'])
def get_students():
    """Fetch students from MySQL, with optional search query support."""
    
    search_query = request.args.get('search_query', '').strip()
    students = []

    try:
        # Connect to MySQL
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SYSARCH"
        )
        cursor = conn.cursor(dictionary=True)

        # Base SQL query
        query = """
            SELECT id, username, firstname, midname, lastname, email, registration_date
            FROM students
        """
        params = []

        # Apply search filter if needed
        if search_query:
            query += """
                WHERE id LIKE %s OR username LIKE %s OR firstname LIKE %s
                OR midname LIKE %s OR lastname LIKE %s OR email LIKE %s
            """
            wildcard_search = f"%{search_query}%"
            params = [wildcard_search] * 6

        cursor.execute(query, params)
        students = cursor.fetchall()

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'An error occurred while fetching student data.'}), 500

    finally:
        cursor.close()
        conn.close()

    return jsonify({'students': students})



#STUDENT PART

@app.route('/student_dashboard')
def student_dashboard():
    if 'username' not in session or session.get('role') != 'student':  
        flash("You need to log in first.", "danger")
        return redirect(url_for('login_dashboard'))

    username = session['username']

    # Connect to MySQL
    conn = mysql.connector.connect(
        host="localhost",
        user="root",  # Change if using a different MySQL user
        password="",  # Add MySQL password if set
        database="SYSARCH"  # Your database name
    )
    cursor = conn.cursor(dictionary=True)  # Fetch results as dictionaries

    # Get student information
    cursor.execute('''
        SELECT id, username, firstname, midname, lastname, 
               course, yearlevel, email, registration_date, remaining_sessions
        FROM students WHERE username = %s
    ''', (username,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        flash("Student record not found.", "danger")
        return redirect(url_for('login_dashboard'))

    # Get lab information
    cursor.execute("SELECT id, roomNumber, capacity FROM labs")
    labs = cursor.fetchall()

    conn.close()  # Close connection

    return render_template('student_dashboard.html', 
                           student=student, 
                           labs=labs,  
                           current_date=date.today().isoformat())

@app.route('/edit_student_record', methods=['GET', 'POST'])
def edit_student_record():
    print("Session Data:", session)

    # Check if user is logged in and is a student
    if 'username' not in session or session.get('role') != 'student':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login_dashboard'))

    # Retrieve username from session
    username = session.get('username')

    # Connect to MySQL
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="SYSARCH"
    )
    cur = conn.cursor(dictionary=True)

    # Fetch student record
    cur.execute("""
        SELECT id, username, password, firstname, lastname, midname, 
               course, yearlevel, email, registration_date, remaining_sessions
        FROM students WHERE username = %s
    """, (username,))
    
    student = cur.fetchone()
    
    # Debugging: Ensure correct data is retrieved
    print("Fetched Student Record:", student)

    if not student:
        flash("Student record not found.", "danger")
        conn.close()
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        try:
            # Collect form data (default to existing values if not provided)
            firstname = request.form.get('firstname', student["firstname"])
            lastname = request.form.get('lastname', student["lastname"])
            midname = request.form.get('midname', student["midname"])
            course = request.form.get('course', student["course"])
            yearlevel = request.form.get('yearlevel', student["yearlevel"])
            email = request.form.get('email', student["email"])

            # Update student record
            cur.execute("""
                UPDATE students 
                SET firstname=%s, lastname=%s, midname=%s, course=%s, yearlevel=%s, email=%s
                WHERE username=%s
            """, (firstname, lastname, midname, course, yearlevel, email, username))
            conn.commit()

            flash("Your record has been updated successfully!", "success")
            return redirect(url_for('student_dashboard'))

        except mysql.connector.Error as e:
            flash(f"Database error: {e}", "danger")

    conn.close()

    return render_template('edit_student_record.html', student=student)

@app.route('/lab_rules_&_regulation')
def lab_rules():
    return render_template('lab_rules_&_regulation.html')

@app.route('/announcements')
def announcements():
    return render_template('announcements.html')

@app.route('/remaining_sessions')
def remaining_sessions():
    return render_template('remaining_sessions.html')

@app.route('/sit_in_rules')
def sit_in_rules():
    return render_template('sit_in_rules.html')

from flask import jsonify, session
import mysql.connector
from datetime import datetime

@app.route('/sit_in_history', methods=['GET'])
def sit_in_history():
    """Fetch and categorize sit-in reservations for the logged-in student using MySQL."""
    username = session.get('username')  # Ensure the student is logged in
    if not username:
        return jsonify({"error": "Unauthorized"}), 403  # Return error if not logged in

    try:
        # Connect to MySQL database
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SYSARCH"
        )
        cursor = conn.cursor(dictionary=True)

        # Fetch all reservations of the logged-in student
        cursor.execute("""
            SELECT datetime, lab_id, status 
            FROM reservations 
            WHERE username = %s
            ORDER BY datetime ASC
        """, (username,))
        sit_in_records = cursor.fetchall()

        # Get current timestamp
        now = datetime.now()

        # Categorize reservations into old, ongoing, and upcoming
        old_reservations = []
        ongoing_reservations = []
        upcoming_reservations = []

        for record in sit_in_records:
            record_datetime = record["datetime"]

            reservation_data = {
                "datetime": record_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "lab_id": record["lab_id"],
                "status": record["status"]
            }

            if record_datetime < now:  # Past reservations
                old_reservations.append(reservation_data)
            elif record_datetime.date() == now.date():  # Same day = Ongoing
                ongoing_reservations.append(reservation_data)
            else:  # Future reservations
                upcoming_reservations.append(reservation_data)

    except mysql.connector.Error as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        # Ensure connection is closed
        cursor.close()
        conn.close()

    return jsonify({
        "old_reservations": old_reservations,
        "ongoing_reservations": ongoing_reservations,
        "upcoming_reservations": upcoming_reservations
    })


@app.route('/make_reservation', methods=['GET', 'POST'])
def make_reservation():
    """Handles lab sit-in reservations and saves them to MySQL (`reservations.db`)."""
    
    if 'username' not in session or session.get('role') != 'student':
        flash("Please log in as a student to reserve a lab.", "warning")
        return redirect(url_for('login_dashboard'))

    username = session['username']
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    try:
        # 🔥 Fetch student's ID based on session username
        cursor.execute("SELECT id FROM students WHERE username = %s", (username,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for('student_dashboard'))        
        
        student_id = student['id']

        # 🔥 Fetch available labs
        cursor.execute("SELECT id, roomNumber, capacity, status FROM labs WHERE status = 'Available'")
        labs = cursor.fetchall()

        if request.method == 'POST':
            lab_id = request.form.get('lab_id')
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 🔥 Check if the selected lab is still available
            cursor.execute("SELECT id FROM labs WHERE id = %s AND status = 'Available'", (lab_id,))
            selected_lab = cursor.fetchone()

            if not selected_lab:
                flash("The selected lab is no longer available.", "danger")
                return redirect(url_for('make_reservation'))

            # 🔥 Insert reservation into MySQL (`reservations.db`)
            cursor.execute("""
                INSERT INTO reservations (student_id, username, lab_id, datetime, status)
                VALUES (%s, %s, %s, %s, 'Pending')
            """, (student_id, username, lab_id, current_datetime))
            conn.commit()

            flash("Lab reservation request submitted successfully!", "success")
            return redirect(url_for('sit_in_history_page'))

    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "danger")
        print(f"Database error: {e}")
    
    finally:
        cursor.close()
        conn.close()

    return render_template('make_reservation.html', labs=labs)

@app.route('/sit_in_records')
def sit_in_records():
    """Fetch all sit-in records from MySQL database and display them."""
    try:
        # Connect to MySQL database
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SYSARCH"
        )
        cur = conn.cursor(dictionary=True)

        # Fetch all sit-in records
        cur.execute("SELECT * FROM sit_in_records")
        records = cur.fetchall()

        conn.close()

        return render_template('sit_in_record.html', records=records)

    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for('student_dashboard'))



# Logout Route
@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login_dashboard'))  # Redirect to login page

if __name__ == '__main__':
    app.run(debug=True, port=3306)
