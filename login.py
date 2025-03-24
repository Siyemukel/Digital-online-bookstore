# login.py

import sqlite3
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from functools import wraps

login_bp = Blueprint('login_bp', __name__)

DATABASE = 'bookstore.db'

def create_connection():
    """Helper to connect to SQLite DB."""
    conn = sqlite3.connect(DATABASE)
    return conn

########################################
# LOGIN ROUTE
########################################
@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Simple login form. 
    1) Checks if user is the hard-coded Admin.
    2) Otherwise checks DB for email/password.
       - If role='student' => user_home2 (the new main approach)
       - If role='staff'   => staff_home
       - If role='driver'  => driver_home
       - Else fallback => home
    """
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # 1) Hard-coded Admin Credentials
        if email == "IamAdmin@gmail.com" and password == "Admin@2004":
            session['user_id'] = 0    # Admin user_id = 0
            session['role'] = 'admin'
            flash("Logged in as Admin!")
            return redirect(url_for('login_bp.admin_home'))

        # 2) Otherwise, check DB for staff/student/driver
        with create_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, password, role FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()

            if row:
                user_id, db_password, role = row

                if db_password == password:
                    # Save user info in session
                    session['user_id'] = user_id
                    session['role'] = role
                    flash("Login successful!")

                    # Check the role
                    if role == 'student':
                        # go to the new second home approach
                        return redirect(url_for('user_bp.user_home2'))
                    elif role == 'staff':
                        return redirect(url_for('login_bp.staff_home'))
                    elif role == 'driver':
                        return redirect(url_for('login_bp.driver_home'))
                    else:
                        # fallback
                        return redirect(url_for('home'))
                else:
                    flash("Invalid password.")
                    return redirect(url_for('login_bp.login'))
            else:
                flash("No user found with that email.")
                return redirect(url_for('login_bp.login'))

    return render_template('login.html')

########################################
# STUDENT HOME PAGE (protected, OLD)
########################################
@login_bp.route('/user_home')
def user_home():
    """
    Old route for students. 
    No longer used for role='student' because we redirect them to user_home2 now.
    We keep it so we don't remove anything.
    """
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Unauthorized access or not logged in.")
        return redirect(url_for('login_bp.login'))

    return render_template('user_home.html')

########################################
# STAFF HOME PAGE (protected)
########################################
@login_bp.route('/staff_home')
def staff_home():
    """
    Page for staff only.
    If session doesn't have user_id or role != 'staff', block access.
    """
    if 'user_id' not in session or session.get('role') != 'staff':
        flash("Unauthorized access or not logged in.")
        return redirect(url_for('login_bp.login'))

    return render_template('staff_home.html')

########################################
# DRIVER HOME PAGE (protected, NEW)
########################################
@login_bp.route('/driver_home')
def driver_home():
    """
    Page for drivers only.
    If session doesn't have user_id or role != 'driver', block access.
    """
    if 'user_id' not in session or session.get('role') != 'driver':
        flash("Unauthorized access or not logged in.")
        return redirect(url_for('login_bp.login'))

    return render_template('driver_home.html')

########################################
# ADMIN HOME PAGE (protected)
########################################
@login_bp.route('/admin_home')
def admin_home():
    """
    Page for admin only (hard-coded user_id=0, role='admin').
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access or not logged in.")
        return redirect(url_for('login_bp.login'))

    return render_template('admin_home.html')

########################################
# DECORATOR EXAMPLE (OPTIONAL)
########################################
def login_required(f):
    """
    Example decorator if you want to protect certain routes. 
    Usage: 
        @login_required
        def some_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function
