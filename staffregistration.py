# staffregistration.py

import sqlite3
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from functools import wraps

staffreg_bp = Blueprint('staffreg_bp', __name__)
DATABASE = 'bookstore.db'

def create_connection():
    """Helper to connect to SQLite DB."""
    conn = sqlite3.connect(DATABASE)
    return conn

########################################
# HELPER: Admin-only Decorator
########################################
def admin_required(f):
    """
    A decorator to ensure only admin can access certain routes.
    If 'role' != 'admin', redirect to /login or somewhere else.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Admin privileges required.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


########################################
# 1) REGISTER STAFF
########################################
@staffreg_bp.route('/register_staff', methods=['GET', 'POST'])
@admin_required
def register_staff():
    """
    Admin-only page to register a new staff member.
    Inserts into 'users' (role='staff') + 'staff' table.
    After success, redirect to staff_management.
    """
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']

        # Basic validations
        if not (email and password and first_name and last_name and phone):
            flash("All fields are required.")
            return redirect(url_for('staffreg_bp.register_staff'))

        with create_connection() as conn:
            cursor = conn.cursor()
            # Check if email is already used
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash("That email is already in use. Please choose another.")
                return redirect(url_for('staffreg_bp.register_staff'))

            # Insert into users + staff
            try:
                cursor.execute("""
                    INSERT INTO users(email, password, role)
                    VALUES (?, ?, ?)
                """, (email, password, 'staff'))
                user_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO staff(user_id, first_name, last_name, phone)
                    VALUES (?, ?, ?, ?)
                """, (user_id, first_name, last_name, phone))

                conn.commit()
                flash("Staff member registered successfully!")
            except Exception as e:
                conn.rollback()
                flash(f"Error: {e}")
                return redirect(url_for('staffreg_bp.register_staff'))

        # On success, redirect to staff_management
        return redirect(url_for('staffreg_bp.staff_management'))

    return render_template('register_staff.html')


########################################
# 2) STAFF MANAGEMENT
########################################
@staffreg_bp.route('/staff_management', methods=['GET'])
@admin_required
def staff_management():
    """
    Admin-only page that lists all staff members.
    Each row has a Delete option.
    Also includes a link to register new Driver for convenience.
    """
    with create_connection() as conn:
        cursor = conn.cursor()
        # Retrieve staff + corresponding user info
        cursor.execute("""
            SELECT s.id, s.first_name, s.last_name, s.phone, u.email
            FROM staff s
            JOIN users u ON s.user_id = u.id
        """)
        staff_list = cursor.fetchall()

    return render_template('staff_management.html', staff_list=staff_list)


########################################
# 3) DELETE STAFF
########################################
@staffreg_bp.route('/delete_staff/<int:staff_id>', methods=['POST'])
@admin_required
def delete_staff(staff_id):
    """
    Deletes the staff record from 'staff' table 
    and also from 'users' table. 
    """
    with create_connection() as conn:
        cursor = conn.cursor()

        # First find the user_id from staff
        cursor.execute("SELECT user_id FROM staff WHERE id = ?", (staff_id,))
        row = cursor.fetchone()
        if not row:
            flash("Staff member not found.")
            return redirect(url_for('staffreg_bp.staff_management'))

        user_id = row[0]

        # Delete from staff
        cursor.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
        # Delete from users
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        flash("Staff member deleted successfully.")

    return redirect(url_for('staffreg_bp.staff_management'))


########################################
# 4) REGISTER DRIVER (NEW)
########################################
@staffreg_bp.route('/register_driver', methods=['GET', 'POST'])
@admin_required
def register_driver():
    """
    Admin-only page to register a new driver.
    Inserts into 'users' (role='driver') + 'drivers' table.
    After success, redirect to driver_management.
    """
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']

        if not (email and password and first_name and last_name and phone):
            flash("All fields are required.")
            return redirect(url_for('staffreg_bp.register_driver'))

        with create_connection() as conn:
            cursor = conn.cursor()
            # Check if email is already used
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash("That email is already in use. Please choose another.")
                return redirect(url_for('staffreg_bp.register_driver'))

            # Insert into users + drivers
            try:
                cursor.execute("""
                    INSERT INTO users(email, password, role)
                    VALUES (?, ?, 'driver')
                """, (email, password))
                user_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO drivers(user_id, first_name, last_name, phone)
                    VALUES (?, ?, ?, ?)
                """, (user_id, first_name, last_name, phone))

                conn.commit()
                flash("Driver registered successfully!")
            except Exception as e:
                conn.rollback()
                flash(f"Error: {e}")
                return redirect(url_for('staffreg_bp.register_driver'))

        # On success, redirect to driver_management
        return redirect(url_for('staffreg_bp.driver_management'))

    return render_template('register_driver.html')


########################################
# 5) DRIVER MANAGEMENT (NEW)
########################################
@staffreg_bp.route('/driver_management', methods=['GET'])
@admin_required
def driver_management():
    """
    Admin-only page that lists all drivers.
    Each row has a Delete option.
    """
    with create_connection() as conn:
        cursor = conn.cursor()
        # Retrieve drivers + corresponding user info
        cursor.execute("""
            SELECT d.id, d.first_name, d.last_name, d.phone, u.email
            FROM drivers d
            JOIN users u ON d.user_id = u.id
        """)
        driver_list = cursor.fetchall()

    return render_template('driver_management.html', driver_list=driver_list)


########################################
# 6) DELETE DRIVER (NEW)
########################################
@staffreg_bp.route('/delete_driver/<int:driver_id>', methods=['POST'])
@admin_required
def delete_driver(driver_id):
    """
    Deletes the driver record from 'drivers' table 
    and also from 'users' table. 
    """
    with create_connection() as conn:
        cursor = conn.cursor()

        # First find the user_id from drivers
        cursor.execute("SELECT user_id FROM drivers WHERE id = ?", (driver_id,))
        row = cursor.fetchone()
        if not row:
            flash("Driver not found.")
            return redirect(url_for('staffreg_bp.driver_management'))

        user_id = row[0]

        # Delete from drivers
        cursor.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
        # Delete from users
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        flash("Driver deleted successfully.")

    return redirect(url_for('staffreg_bp.driver_management'))
