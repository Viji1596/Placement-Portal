from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from email.message import EmailMessage
import os
import random
import smtplib
import sqlite3
from functools import wraps
import json

app = Flask(__name__)

def format_requirements(criteria_str):
    if not criteria_str:
        return ""
    try:
        data = json.loads(criteria_str)
        if not isinstance(data, dict):
            return str(criteria_str)
            
        req_type = data.get('requirement_type', '')
        parts = []
        if req_type:
            parts.append(f"Requirement: {req_type}")
        
        if req_type in ['10th', '12th']:
            if data.get('min_percentage'):
                parts.append(f"Min Percentage: {data.get('min_percentage')}%")
        elif req_type in ['UG', 'PG']:
            if data.get('min_cgpa'):
                parts.append(f"Min CGPA: {data.get('min_cgpa')}")
            if data.get('degree'):
                parts.append(f"Degree: {data.get('degree')}")
                
        return " | ".join(parts) if parts else str(criteria_str)
    except Exception:
        return str(criteria_str)

app.jinja_env.filters['format_requirements'] = format_requirements
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('placement_portal.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'company', 'student')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create companies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            hr_contact TEXT NOT NULL,
            website TEXT,
            address TEXT,
            approval_status TEXT DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected', 'blacklisted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            contact_number TEXT NOT NULL,
            email TEXT NOT NULL,
            course TEXT,
            year INTEGER,
            cgpa REAL,
            resume_path TEXT,
            profile_picture_path TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create placement_drives table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS placement_drives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            job_description TEXT NOT NULL,
            eligibility_criteria TEXT NOT NULL,
            application_deadline DATE NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'closed')),
            location TEXT,
            salary_range TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')
    
    # Create applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            drive_id INTEGER NOT NULL,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'applied' CHECK(status IN ('applied', 'shortlisted', 'selected', 'rejected')),
            remarks TEXT,
            UNIQUE(student_id, drive_id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (drive_id) REFERENCES placement_drives(id)
        )
    ''')

    # Create password_resets table for OTP-based password reset
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            otp TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    # Add new columns to students table if they don't exist
    try:
        cursor.execute('ALTER TABLE students ADD COLUMN profile_picture_path TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE students ADD COLUMN year INTEGER')
        # Migrate existing text year values to integers
        cursor.execute('UPDATE students SET year = CAST(year AS INTEGER) WHERE year IS NOT NULL AND year != ""')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create admin user if not exists
    cursor.execute('SELECT * FROM users WHERE role = ?', ('admin',))
    admin = cursor.fetchone()
    if not admin:
        admin_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@placement.com', admin_password, 'admin'))
    
    conn.commit()
    conn.close()


def generate_otp():
    """Generate a 6-digit numeric OTP."""
    return f"{random.randint(100000, 999999)}"


def send_otp_email(to_email, otp):
    """
    Send OTP email. For local/demo use, if SMTP settings are not provided,
    the OTP will be printed to the console.
    Always prints to console for easy testing.
    """
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '465'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    email_from = os.getenv('EMAIL_FROM', smtp_username or 'no-reply@example.com')

    subject = 'Placement Portal - Password Reset OTP'
    body = f"Your OTP for resetting your password is {otp}. It is valid for 10 minutes."

    # Always print to console for demo/testing
    print("\n" + "="*60)
    print(f"[OTP EMAIL] To: {to_email}")
    print(f"[OTP EMAIL] Subject: {subject}")
    print(f"[OTP EMAIL] OTP Code: {otp}")
    print(f"[OTP EMAIL] Valid for: 10 minutes")
    print("="*60 + "\n")

    # If SMTP is not configured, return after printing
    if not smtp_server or not smtp_username or not smtp_password:
        print(f"[INFO] SMTP not configured. OTP printed above. Configure SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD environment variables to send real emails.")
        return

    # Try to send email if SMTP is configured
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = email_from
        msg['To'] = to_email
        msg.set_content(body)

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        print(f"[SUCCESS] OTP email sent successfully to {to_email}")
    except Exception as e:
        # Fallback to console if email sending fails
        print(f"[ERROR] Failed to send OTP email: {e}")
        print(f"[INFO] OTP is still available above for testing purposes.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def company_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'company':
            flash('Company access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        # Try to find user by username or email
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username_or_email, username_or_email)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Check if company is approved
            if user['role'] == 'company':
                conn = get_db_connection()
                company = conn.execute('SELECT approval_status FROM companies WHERE user_id = ?', (user['id'],)).fetchone()
                conn.close()
                if company and company['approval_status'] != 'approved':
                    flash('Your company registration is pending approval.', 'warning')
                    return redirect(url_for('company_dashboard'))
            
            # Check if student is blacklisted
            if user['role'] == 'student':
                conn = get_db_connection()
                student = conn.execute('SELECT status FROM students WHERE user_id = ?', (user['id'],)).fetchone()
                conn.close()
                if student and student['status'] == 'blacklisted':
                    session.clear()
                    flash('Your account has been blacklisted. Contact admin.', 'danger')
                    return redirect(url_for('login'))
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'company':
                return redirect(url_for('company_dashboard'))
            elif user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username/email or password.', 'danger')
    
    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Step 1: User enters username or email to receive an OTP.
    """
    if request.method == 'POST':
        identifier = request.form.get('identifier')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? OR email = ?',
            (identifier, identifier)
        ).fetchone()

        if not user:
            conn.close()
            flash('No user found with that username or email.', 'danger')
            return render_template('forgot_password.html')

        otp = generate_otp()
        expires_at = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')

        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO password_resets (user_id, otp, expires_at)
            VALUES (?, ?, ?)
            ''',
            (user['id'], otp, expires_at)
        )
        token_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Store token id and email in session for subsequent steps
        session['reset_token_id'] = token_id
        session['reset_email'] = user['email']
        # Reset OTP attempt counter whenever a new OTP is generated
        session['otp_attempts'] = 0

        # Send OTP to registered email (or print to console in demo mode)
        send_otp_email(user['email'], otp)

        flash('An OTP has been sent to your registered email address.', 'info')
        return redirect(url_for('verify_otp'))

    return render_template('forgot_password.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """
    Step 2: Verify the OTP typed by the user matches the one sent.
    """
    token_id = session.get('reset_token_id')
    if not token_id:
        flash('No password reset request found. Please start again.', 'warning')
        return redirect(url_for('forgot_password'))

    # Maximum number of OTP attempts allowed
    max_attempts = 3
    current_attempts = session.get('otp_attempts', 0)

    if request.method == 'POST':
        typed_otp = request.form.get('otp')
        conn = get_db_connection()
        token = conn.execute(
            '''
            SELECT * FROM password_resets
            WHERE id = ? AND used = 0
            ''',
            (token_id,)
        ).fetchone()

        if not token:
            conn.close()
            flash('Invalid or expired OTP request. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))

        # Check expiry
        try:
            expires_at = datetime.strptime(token['expires_at'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            expires_at = datetime.now()

        if expires_at < datetime.now():
            conn.close()
            flash('OTP has expired. Please request a new one.', 'danger')
            return redirect(url_for('forgot_password'))

        if typed_otp != token['otp']:
            # Increment OTP attempt counter on each invalid attempt
            current_attempts = session.get('otp_attempts', 0) + 1
            session['otp_attempts'] = current_attempts

            # If attempts exceed or reach max, invalidate the reset flow
            if current_attempts >= max_attempts:
                # Mark this token as used to prevent further attempts
                conn.execute('UPDATE password_resets SET used = 1 WHERE id = ?', (token_id,))
                conn.commit()
                conn.close()

                # Clear reset-related session data
                session.pop('reset_token_id', None)
                session.pop('reset_email', None)
                session.pop('reset_user_id', None)
                session.pop('otp_attempts', None)

                flash('Too many invalid OTP attempts. Please request a new OTP.', 'danger')
                return redirect(url_for('forgot_password'))

            conn.close()
            attempts_left = max_attempts - current_attempts
            flash(f'Invalid OTP. You have {attempts_left} attempts left.', 'danger')
            return render_template(
                'verify_otp.html',
                email=session.get('reset_email'),
                attempts_left=attempts_left,
                max_attempts=max_attempts
            )

        # Mark token as used and allow password reset
        conn.execute('UPDATE password_resets SET used = 1 WHERE id = ?', (token_id,))
        conn.commit()
        session['reset_user_id'] = token['user_id']
        conn.close()

        # Reset OTP attempts on successful verification
        session.pop('otp_attempts', None)

        flash('OTP verified successfully. Please set a new password.', 'success')
        return redirect(url_for('reset_password'))

    # For GET requests, just show how many attempts are available (if any have been used)
    attempts_left = max_attempts - current_attempts
    return render_template(
        'verify_otp.html',
        email=session.get('reset_email'),
        attempts_left=attempts_left,
        max_attempts=max_attempts
    )


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """
    Step 3: User sets a new password which is updated in the database.
    """
    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Password reset session has expired. Please request a new OTP.', 'warning')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('Please fill in all fields.', 'danger')
            return render_template('reset_password.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        conn.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (hashed_password, user_id)
        )
        conn.commit()
        conn.close()

        # Clear reset session data
        session.pop('reset_user_id', None)
        session.pop('reset_token_id', None)
        session.pop('reset_email', None)

        flash('Your password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name')
        hr_contact = request.form.get('hr_contact')
        website = request.form.get('website')
        address = request.form.get('address')
        
        conn = get_db_connection()
        
        # Check if username or email already exists
        existing_user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing_user:
            flash('Username or email already exists.', 'danger')
            conn.close()
            return render_template('register_company.html')
        
        # Create user
        hashed_password = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', (username, email, hashed_password, 'company'))
        user_id = cursor.lastrowid
        
        # Create company profile
        cursor.execute('''
            INSERT INTO companies (user_id, company_name, hr_contact, website, address)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, company_name, hr_contact, website, address))
        
        conn.commit()
        conn.close()
        
        flash('Company registration successful! Please wait for admin approval.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_company.html')

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        student_name = request.form.get('student_name')
        student_id = request.form.get('student_id')
        contact_number = request.form.get('contact_number')
        course = request.form.get('course')
        year = request.form.get('year')
        cgpa = request.form.get('cgpa')
        
        conn = get_db_connection()
        
        # Check if username, email, or student_id already exists
        existing_user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        existing_student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
        
        if existing_user or existing_student:
            flash('Username, email, or student ID already exists.', 'danger')
            conn.close()
            return render_template('register_student.html')
        
        # Create user
        hashed_password = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', (username, email, hashed_password, 'student'))
        user_id = cursor.lastrowid
        
        # Create student profile
        cursor.execute('''
            INSERT INTO students (user_id, student_name, student_id, contact_number, email, course, year, cgpa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, student_name, student_id, contact_number, email, course, int(year) if year else None, cgpa))
        
        conn.commit()
        conn.close()
        
        flash('Student registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_student.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Admin Routes
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    total_students = conn.execute('SELECT COUNT(*) as count FROM students').fetchone()['count']
    total_companies = conn.execute('SELECT COUNT(*) as count FROM companies').fetchone()['count']
    total_applications = conn.execute('SELECT COUNT(*) as count FROM applications').fetchone()['count']
    total_drives = conn.execute('SELECT COUNT(*) as count FROM placement_drives').fetchone()['count']
    
    pending_companies = conn.execute('SELECT COUNT(*) as count FROM companies WHERE approval_status = ?', ('pending',)).fetchone()['count']
    pending_drives = conn.execute('SELECT COUNT(*) as count FROM placement_drives WHERE status = ?', ('pending',)).fetchone()['count']
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_companies=total_companies,
                         total_applications=total_applications,
                         total_drives=total_drives,
                         pending_companies=pending_companies,
                         pending_drives=pending_drives)

@app.route('/admin/companies')
@admin_required
def admin_companies():
    search = request.args.get('search', '')
    conn = get_db_connection()
    
    if search:
        companies = conn.execute('''
            SELECT c.*, u.email, u.username
            FROM companies c
            JOIN users u ON c.user_id = u.id
            WHERE c.company_name LIKE ?
            ORDER BY c.created_at DESC
        ''', (f'%{search}%',)).fetchall()
    else:
        companies = conn.execute('''
            SELECT c.*, u.email, u.username
            FROM companies c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
        ''').fetchall()
    conn.close()
    return render_template('admin/companies.html', companies=companies, search=search)

@app.route('/admin/companies/<int:company_id>/approve', methods=['POST'])
@admin_required
def approve_company(company_id):
    conn = get_db_connection()
    conn.execute('UPDATE companies SET approval_status = ? WHERE id = ?', ('approved', company_id))
    conn.commit()
    conn.close()
    flash('Company approved successfully.', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/companies/<int:company_id>/reject', methods=['POST'])
@admin_required
def reject_company(company_id):
    conn = get_db_connection()
    conn.execute('UPDATE companies SET approval_status = ? WHERE id = ?', ('rejected', company_id))
    conn.commit()
    conn.close()
    flash('Company rejected.', 'info')
    return redirect(url_for('admin_companies'))

@app.route('/admin/companies/<int:company_id>/blacklist', methods=['POST'])
@admin_required
def blacklist_company(company_id):
    conn = get_db_connection()
    conn.execute('UPDATE companies SET approval_status = ? WHERE id = ?', ('blacklisted', company_id))
    conn.commit()
    conn.close()
    flash('Company blacklisted.', 'warning')
    return redirect(url_for('admin_companies'))

@app.route('/admin/students')
@admin_required
def admin_students():
    search = request.args.get('search', '')
    conn = get_db_connection()
    
    if search:
        students = conn.execute('''
            SELECT s.*, u.email, u.username
            FROM students s
            JOIN users u ON s.user_id = u.id
            WHERE s.student_name LIKE ? OR s.student_id LIKE ? OR s.contact_number LIKE ? OR s.email LIKE ?
            ORDER BY s.created_at DESC
        ''', (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        students = conn.execute('''
            SELECT s.*, u.email, u.username
            FROM students s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
        ''').fetchall()
    
    conn.close()
    return render_template('admin/students.html', students=students, search=search)

@app.route('/admin/students/<int:student_id>/blacklist', methods=['POST'])
@admin_required
def blacklist_student(student_id):
    conn = get_db_connection()
    conn.execute('UPDATE students SET status = ? WHERE id = ?', ('blacklisted', student_id))
    conn.commit()
    conn.close()
    flash('Student blacklisted.', 'warning')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/<int:student_id>/activate', methods=['POST'])
@admin_required
def activate_student(student_id):
    conn = get_db_connection()
    conn.execute('UPDATE students SET status = ? WHERE id = ?', ('active', student_id))
    conn.commit()
    conn.close()
    flash('Student activated.', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/<int:student_id>/profile')
@admin_required
def admin_view_student_profile(student_id):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    
    if not student:
        flash('Student not found.', 'danger')
        conn.close()
        return redirect(url_for('admin_students'))
    
    applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.application_deadline, c.company_name, pd.status as drive_status
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.application_date DESC
    ''', (student_id,)).fetchall()
    
    conn.close()
    return render_template('admin/student_profile.html', student=student, applications=applications)

@app.route('/admin/drives')
@admin_required
def admin_drives():
    conn = get_db_connection()
    drives = conn.execute('''
        SELECT pd.*, c.company_name
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        ORDER BY pd.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/drives.html', drives=drives)

@app.route('/admin/drives/<int:drive_id>/approve', methods=['POST'])
@admin_required
def approve_drive(drive_id):
    conn = get_db_connection()
    conn.execute('UPDATE placement_drives SET status = ? WHERE id = ?', ('approved', drive_id))
    conn.commit()
    conn.close()
    flash('Placement drive approved.', 'success')
    return redirect(url_for('admin_drives'))

@app.route('/admin/drives/<int:drive_id>/reject', methods=['POST'])
@admin_required
def reject_drive(drive_id):
    conn = get_db_connection()
    conn.execute('UPDATE placement_drives SET status = ? WHERE id = ?', ('closed', drive_id))
    conn.commit()
    conn.close()
    flash('Placement drive rejected.', 'info')
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@admin_required
def admin_applications():
    conn = get_db_connection()
    applications = conn.execute('''
        SELECT a.*, s.student_name, s.student_id, pd.job_title, c.company_name
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        ORDER BY a.application_date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/applications.html', applications=applications)

# Company Routes
@app.route('/company/dashboard')
@company_required
def company_dashboard():
    conn = get_db_connection()
    company = conn.execute('''
        SELECT c.*, u.email, u.username
        FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    drives = conn.execute('''
        SELECT pd.*, COUNT(a.id) as applicant_count
        FROM placement_drives pd
        LEFT JOIN applications a ON pd.id = a.drive_id
        WHERE pd.company_id = ?
        GROUP BY pd.id
        ORDER BY pd.created_at DESC
    ''', (company['id'],)).fetchall()
    
    conn.close()
    return render_template('company/dashboard.html', company=company, drives=drives)

@app.route('/company/drives/create', methods=['GET', 'POST'])
@company_required
def create_drive():
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    
    if company['approval_status'] != 'approved':
        flash('Your company must be approved by admin before creating placement drives.', 'warning')
        conn.close()
        return redirect(url_for('company_dashboard'))
    
    if request.method == 'POST':
        job_title = request.form.get('job_title')
        job_description = request.form.get('job_description')
        
        requirement_type = request.form.get('requirement_type')
        min_percentage = request.form.get('min_percentage')
        min_cgpa = request.form.get('min_cgpa')
        degree = request.form.get('degree')
        
        criteria_dict = {
            'requirement_type': requirement_type,
            'min_percentage': min_percentage,
            'min_cgpa': min_cgpa,
            'degree': degree
        }
        eligibility_criteria = json.dumps(criteria_dict)
        
        application_deadline = request.form.get('application_deadline')
        location = request.form.get('location')
        salary_range = request.form.get('salary_range')
        
        conn.execute('''
            INSERT INTO placement_drives (company_id, job_title, job_description, eligibility_criteria, application_deadline, location, salary_range)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (company['id'], job_title, job_description, eligibility_criteria, application_deadline, location, salary_range))
        conn.commit()
        conn.close()
        
        flash('Placement drive created successfully! Waiting for admin approval.', 'success')
        return redirect(url_for('company_dashboard'))
    
    conn.close()
    return render_template('company/create_drive.html')

@app.route('/company/drives/<int:drive_id>/edit', methods=['GET', 'POST'])
@company_required
def edit_drive(drive_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?', (drive_id, company['id'])).fetchone()
    
    if not drive:
        flash('Drive not found.', 'danger')
        conn.close()
        return redirect(url_for('company_dashboard'))
    
    if request.method == 'POST':
        requirement_type = request.form.get('requirement_type')
        min_percentage = request.form.get('min_percentage')
        min_cgpa = request.form.get('min_cgpa')
        degree = request.form.get('degree')
        
        criteria_dict = {
            'requirement_type': requirement_type,
            'min_percentage': min_percentage,
            'min_cgpa': min_cgpa,
            'degree': degree
        }
        eligibility_criteria = json.dumps(criteria_dict)
        
        conn.execute('''
            UPDATE placement_drives
            SET job_title = ?, job_description = ?, eligibility_criteria = ?, application_deadline = ?, location = ?, salary_range = ?
            WHERE id = ?
        ''', (request.form.get('job_title'), request.form.get('job_description'), 
              eligibility_criteria, request.form.get('application_deadline'),
              request.form.get('location'), request.form.get('salary_range'), drive_id))
        conn.commit()
        conn.close()
        flash('Drive updated successfully.', 'success')
        return redirect(url_for('company_dashboard'))
    
    parsed_reqs = {}
    try:
        parsed_reqs = json.loads(drive['eligibility_criteria'])
    except Exception:
        parsed_reqs = {'raw': drive['eligibility_criteria']}
        
    conn.close()
    return render_template('company/edit_drive.html', drive=drive, parsed_reqs=parsed_reqs)

@app.route('/company/drives/<int:drive_id>/delete', methods=['POST'])
@company_required
def delete_drive(drive_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?', (drive_id, company['id'])).fetchone()
    
    if drive:
        conn.execute('DELETE FROM placement_drives WHERE id = ?', (drive_id,))
        conn.commit()
        flash('Drive deleted successfully.', 'success')
    
    conn.close()
    return redirect(url_for('company_dashboard'))

@app.route('/company/drives/<int:drive_id>/close', methods=['POST'])
@company_required
def close_drive(drive_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?', (drive_id, company['id'])).fetchone()
    
    if drive:
        conn.execute('UPDATE placement_drives SET status = ? WHERE id = ?', ('closed', drive_id))
        conn.commit()
        flash('Drive closed successfully.', 'success')
    
    conn.close()
    return redirect(url_for('company_dashboard'))

@app.route('/company/drives/<int:drive_id>/applications')
@company_required
def view_applications(drive_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?', (drive_id, company['id'])).fetchone()
    
    if not drive:
        flash('Drive not found.', 'danger')
        conn.close()
        return redirect(url_for('company_dashboard'))
    
    applications = conn.execute('''
        SELECT a.*, s.student_name, s.student_id, s.email, s.contact_number, s.course, s.year, s.cgpa
        FROM applications a
        JOIN students s ON a.student_id = s.id
        WHERE a.drive_id = ?
        ORDER BY a.application_date DESC
    ''', (drive_id,)).fetchall()
    
    conn.close()
    return render_template('company/applications.html', drive=drive, applications=applications)

@app.route('/company/applications/<int:application_id>/update', methods=['POST'])
@company_required
def update_application_status(application_id):
    status = request.form.get('status')
    remarks = request.form.get('remarks', '')
    
    conn = get_db_connection()
    application = conn.execute('SELECT * FROM applications WHERE id = ?', (application_id,)).fetchone()
    
    if application:
        drive = conn.execute('SELECT * FROM placement_drives WHERE id = ?', (application['drive_id'],)).fetchone()
        company = conn.execute('SELECT * FROM companies WHERE id = ? AND user_id = ?', (drive['company_id'], session['user_id'])).fetchone()
        
        if company:
            conn.execute('UPDATE applications SET status = ?, remarks = ? WHERE id = ?', (status, remarks, application_id))
            conn.commit()
            flash('Application status updated.', 'success')
    
    conn.close()
    return redirect(url_for('view_applications', drive_id=application['drive_id']))

@app.route('/company/students/<int:student_id>/profile')
@company_required
def company_view_student_profile(student_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
    
    # Check if the company has any applications from this student
    has_application = conn.execute('''
        SELECT COUNT(*) as count
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        WHERE a.student_id = ? AND pd.company_id = ?
    ''', (student_id, company['id'])).fetchone()
    
    if has_application['count'] == 0:
        flash('You can only view profiles of students who have applied to your drives.', 'danger')
        conn.close()
        return redirect(url_for('company_dashboard'))
    
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    
    if not student:
        flash('Student not found.', 'danger')
        conn.close()
        return redirect(url_for('company_dashboard'))
    
    applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.application_deadline, c.company_name, pd.status as drive_status
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ? AND pd.company_id = ?
        ORDER BY a.application_date DESC
    ''', (student_id, company['id'])).fetchall()
    
    conn.close()
    return render_template('company/student_profile.html', student=student, applications=applications)

# Student Routes
@app.route('/student/dashboard')
@student_required
def student_dashboard():
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session['user_id'],)).fetchone()
    
    notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE student_id = ? AND is_read = 0
        ORDER BY created_at DESC
    ''', (student['id'],)).fetchall()
    
    # Get all approved drives that haven't passed deadline
    all_drives = conn.execute('''
        SELECT pd.*, c.company_name, 
               CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied,
               a.status as application_status
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        LEFT JOIN applications a ON pd.id = a.drive_id AND a.student_id = ?
        WHERE pd.status = 'approved' AND pd.application_deadline >= date('now')
        ORDER BY pd.created_at DESC
    ''', (student['id'],)).fetchall()
    
    # Filter drives based on eligibility
    approved_drives = []
    student_cgpa = float(student['cgpa']) if student['cgpa'] else 0.0
    student_course = (student['course'] or '').lower()
    
    for drive in all_drives:
        is_eligible = True
        try:
            criteria = json.loads(drive['eligibility_criteria'])
            req_type = criteria.get('requirement_type')
            
            if req_type in ['UG', 'PG']:
                # Check CGPA
                min_cgpa = criteria.get('min_cgpa')
                if min_cgpa:
                    min_cgpa_val = float(min_cgpa)
                    if student_cgpa < min_cgpa_val:
                        is_eligible = False
                
                # Check degree/course
                req_degree = criteria.get('degree')
                if req_degree and is_eligible:
                    if req_degree.lower() not in student_course:
                        is_eligible = False
                        
        except Exception:
            # If criteria parsing fails, assume eligible
            pass
            
        if is_eligible:
            approved_drives.append(drive)
    
    my_applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.application_deadline, c.company_name
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.application_date DESC
    ''', (student['id'],)).fetchall()
    
    conn.close()
    return render_template('student/dashboard.html', student=student, approved_drives=approved_drives, my_applications=my_applications, notifications=notifications)

@app.route('/student/profile', methods=['GET', 'POST'])
@student_required
def student_profile():
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session['user_id'],)).fetchone()
    
    if request.method == 'POST':
        student_name = request.form.get('student_name')
        contact_number = request.form.get('contact_number')
        course = request.form.get('course')
        year = request.form.get('year')
        cgpa = request.form.get('cgpa')
        
        # Handle profile picture upload
        profile_picture_path = student['profile_picture_path']
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_image_file(file.filename):
                filename = secure_filename(f"{student['student_id']}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                profile_picture_path = f"uploads/resumes/{filename}"
                
                # Delete old profile picture if exists
                if student['profile_picture_path']:
                    old_path = os.path.join('static', student['profile_picture_path'])
                    if os.path.exists(old_path):
                        os.remove(old_path)
        
        # Handle resume upload
        resume_path = student['resume_path']
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{student['student_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                resume_path = f"uploads/resumes/{filename}"
                
                # Delete old resume if exists
                if student['resume_path']:
                    old_path = os.path.join('static', student['resume_path'])
                    if os.path.exists(old_path):
                        os.remove(old_path)
        
        conn.execute('''
            UPDATE students
            SET student_name = ?, contact_number = ?, course = ?, year = ?, cgpa = ?, resume_path = ?, profile_picture_path = ?
            WHERE id = ?
        ''', (student_name, contact_number, course, int(year) if year else None, cgpa, resume_path, profile_picture_path, student['id']))
        
        # Check eligibility for applied drives
        applications = conn.execute('''
            SELECT a.id as app_id, pd.id as drive_id, pd.eligibility_criteria, pd.job_title, c.company_name
            FROM applications a
            JOIN placement_drives pd ON a.drive_id = pd.id
            JOIN companies c ON pd.company_id = c.id
            WHERE a.student_id = ?
        ''', (student['id'],)).fetchall()
        
        student_cgpa = float(cgpa) if cgpa else 0.0
        student_course = (course or '').lower()
        
        for app_rec in applications:
            try:
                criteria = json.loads(app_rec['eligibility_criteria'])
                req_type = criteria.get('requirement_type')
                
                ineligible = False
                ineligible_reason = ""
                
                if req_type in ['UG', 'PG']:
                    min_cgpa = criteria.get('min_cgpa')
                    if min_cgpa:
                        min_cgpa_val = float(min_cgpa)
                        if student_cgpa < min_cgpa_val:
                            ineligible = True
                            ineligible_reason = f"CGPA ({student_cgpa}) is below required {min_cgpa_val}."
                    
                    req_degree = criteria.get('degree')
                    if req_degree and not ineligible:
                        if req_degree.lower() not in student_course:
                            ineligible = True
                            ineligible_reason = f"Course doesn't match degree ({req_degree})."
                
                if ineligible:
                    # Remove application and notify
                    conn.execute('DELETE FROM applications WHERE id = ?', (app_rec['app_id'],))
                    message = f"You were automatically removed from the drive '{app_rec['job_title']}' at {app_rec['company_name']} because your updated profile no longer meets the eligibility criteria: {ineligible_reason}"
                    conn.execute('INSERT INTO notifications (student_id, message) VALUES (?, ?)', (student['id'], message))
                    
            except Exception:
                pass 
        
        conn.commit()
        flash('Profile updated successfully.', 'success')
        conn.close()
        return redirect(url_for('student_profile'))
    
    # GET request - fetch application data
    applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.application_deadline, c.company_name, pd.status as drive_status
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.application_date DESC
    ''', (student['id'],)).fetchall()
    
    conn.close()
    return render_template('student/profile.html', student=student, applications=applications)

@app.route('/student/drives/<int:drive_id>/apply', methods=['POST'])
@student_required
def apply_drive(drive_id):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session['user_id'],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND status = ?', (drive_id, 'approved')).fetchone()
    
    if not drive:
        flash('Drive not found or not approved.', 'danger')
        conn.close()
        return redirect(url_for('student_dashboard'))
    
    # Check if already applied
    existing = conn.execute('SELECT * FROM applications WHERE student_id = ? AND drive_id = ?', (student['id'], drive_id)).fetchone()
    if existing:
        flash('You have already applied for this drive.', 'warning')
        conn.close()
        return redirect(url_for('student_dashboard'))
    
    # Check deadline
    if datetime.strptime(drive['application_deadline'], '%Y-%m-%d').date() < datetime.now().date():
        flash('Application deadline has passed.', 'danger')
        conn.close()
        return redirect(url_for('student_dashboard'))
    
    # Check if resume is uploaded
    if not student['resume_path']:
        flash('You must upload a resume before applying for placement drives.', 'danger')
        conn.close()
        return redirect(url_for('student_profile'))
    
    # Check eligibility criteria
    try:
        criteria = json.loads(drive['eligibility_criteria'])
        req_type = criteria.get('requirement_type')
        
        ineligible = False
        ineligible_reason = ""
        
        if req_type in ['UG', 'PG']:
            # Check CGPA
            min_cgpa = criteria.get('min_cgpa')
            if min_cgpa:
                min_cgpa_val = float(min_cgpa)
                student_cgpa = float(student['cgpa']) if student['cgpa'] else 0.0
                if student_cgpa < min_cgpa_val:
                    ineligible = True
                    ineligible_reason = f"Your CGPA ({student_cgpa}) is below the required {min_cgpa_val}."
            
            # Check degree/course
            req_degree = criteria.get('degree')
            if req_degree and not ineligible:
                student_course = (student['course'] or '').lower()
                if req_degree.lower() not in student_course:
                    ineligible = True
                    ineligible_reason = f"Your course doesn't match the required degree ({req_degree})."
        
        if ineligible:
            flash(f'You are not eligible for this drive: {ineligible_reason}', 'danger')
            conn.close()
            return redirect(url_for('student_dashboard'))
            
    except Exception as e:
        # If criteria parsing fails, allow application but log the error
        print(f"Error parsing eligibility criteria: {e}")
    
    conn.execute('''
        INSERT INTO applications (student_id, drive_id)
        VALUES (?, ?)
    ''', (student['id'], drive_id))
    conn.commit()
    conn.close()
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/applications')
@student_required
def student_applications():
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session['user_id'],)).fetchone()
    
    applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.application_deadline, c.company_name, pd.status as drive_status
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.application_date DESC
    ''', (student['id'],)).fetchall()
    
    conn.close()
    return render_template('student/applications.html', applications=applications)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

