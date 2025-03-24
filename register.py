# register.py

import sqlite3, time, random, smtplib
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create a Blueprint for the registration module
register_bp = Blueprint('register_bp', __name__)

# Email credentials (use your latest app password)
FROM_EMAIL = "sandileisaacmbonambi@gmail.com"
FROM_PASSWORD = "ziwrzlbsyfbjlwst"

# We can store the DB name here or import from app.py
DATABASE = 'bookstore.db'

def create_connection():
    """Helper to connect to SQLite DB."""
    conn = sqlite3.connect(DATABASE)
    return conn

########################################
# 1) STEP ONE: Enter email & send OTP
########################################
@register_bp.route('/request_email', methods=['GET', 'POST'])
def request_email():
    """User enters an email; we generate OTP and email it."""
    if request.method == 'POST':
        email = request.form['email']

        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))

        # Store OTP + email + expiration in session
        session['pending_email'] = email
        session['otp'] = otp
        session['otp_expiry'] = time.time() + 300  # 5 minutes

        # Send email with OTP
        send_otp_email(email, otp)

        flash("An OTP has been sent to your email. Please verify.")
        return redirect(url_for('register_bp.verify_otp'))
    return render_template('request_email.html')

########################################
# 2) STEP TWO: Verify the OTP
########################################
@register_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    """
    Page where the user enters the OTP.
    If it matches and isn't expired, proceed to the full registration form.
    """
    if request.method == 'POST':
        user_otp = request.form['otp']

        # Check stored OTP and expiry
        original_otp = session.get('otp')
        expiry = session.get('otp_expiry')

        if original_otp and expiry:
            if time.time() > expiry:
                flash("OTP has expired. Please start again.")
                return redirect(url_for('register_bp.request_email'))

            if user_otp == original_otp:
                flash("OTP verified successfully! Please complete registration.")
                return redirect(url_for('register_bp.register_student'))
            else:
                flash("Invalid OTP. Please try again or re-enter email.")
                return redirect(url_for('register_bp.verify_otp'))
        else:
            flash("No OTP in session. Please start again.")
            return redirect(url_for('register_bp.request_email'))

    return render_template('verify_otp.html')

########################################
# 3) STEP THREE: Register Student
########################################
@register_bp.route('/register_student', methods=['GET', 'POST'])
def register_student():
    """
    After OTP verification, display the registration form (email is read-only).
    """
    email = session.get('pending_email')
    if not email:
        flash("Session expired or missing. Please start again.")
        return redirect(url_for('register_bp.request_email'))

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        password = request.form['password']

        # Basic validation
        if not (first_name and last_name and phone and password):
            flash("All fields are required.")
            return redirect(url_for('register_bp.register_student'))

        # Insert into DB
        with create_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users(email, password, role) VALUES (?, ?, ?)",
                    (email, password, 'student')
                )
                user_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO students(user_id, first_name, last_name, phone)
                    VALUES (?, ?, ?, ?)
                """, (user_id, first_name, last_name, phone))

                conn.commit()
                flash("Registration successful! You can now log in.")
            except Exception as e:
                conn.rollback()
                flash(f"Error: {str(e)}")
                return redirect(url_for('register_bp.register_student'))

        # Clear session data
        session.pop('otp', None)
        session.pop('otp_expiry', None)
        session.pop('pending_email', None)

        # <-- Changed here: redirect to the login page
        return redirect(url_for('login_bp.login'))

    return render_template('register_student.html', email=email)

########################################
# HELPER: Send Email via SSL (port 465)
########################################
def send_otp_email(to_email, otp):
    """
    Sends an OTP using Gmail SMTP over SSL (port 465).
    """
    subject = "Your OTP Code"
    body = f"Your One-Time Password is: {otp}\nIt will expire in 5 minutes."

    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect with SSL on port 465
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(FROM_EMAIL, FROM_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("OTP Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
