# delivery.py

import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps

delivery_bp = Blueprint('delivery_bp', __name__, url_prefix='/delivery')
DATABASE = 'bookstore.db'

def create_connection():
    return sqlite3.connect(DATABASE)

def user_required(f):
    """Requires a logged-in user with 'user_id' in session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

########################################
# 1) MY DELIVERIES (User-Side)
########################################
@delivery_bp.route('/my_deliveries')
@user_required
def my_deliveries():
    """
    Shows all deliveries for the logged-in user in descending order.
    A 'delivery' references a purchase_id, which in turn belongs to a user_id.
    We'll join deliveries -> purchases -> check user_id.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        # For each delivery, we can show purchase_id, payment_date, status, etc.
        c.execute("""
            SELECT d.id, d.purchase_id, d.status, d.address, d.delivered_date, p.payment_date
            FROM deliveries d
            JOIN purchases p ON d.purchase_id = p.id
            WHERE p.user_id = ?
            ORDER BY d.id DESC
        """, (user_id,))
        deliveries = c.fetchall()

    return render_template('my_deliveries.html', deliveries=deliveries)

########################################
# 2) TRACK DELIVERY (User-Side)
########################################
@delivery_bp.route('/track_delivery/<int:delivery_id>')
@user_required
def track_delivery(delivery_id):
    """
    Displays a 4-step line bar with the statuses:
      1) Pending
      2) Driver Assigned
      3) Pick Up Confirmed
      4) Delivered
    Only if this delivery belongs to the logged-in user.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        # Make sure the user is the owner
        c.execute("""
            SELECT d.id, d.status
            FROM deliveries d
            JOIN purchases p ON d.purchase_id = p.id
            WHERE d.id = ? AND p.user_id = ?
        """, (delivery_id, user_id))
        row = c.fetchone()
        if not row:
            flash("Delivery not found or you do not own it.")
            return redirect(url_for('delivery_bp.my_deliveries'))

        # We have the current status
        current_status = row[1]

    # Pass the status to the template
    return render_template('track_delivery.html', delivery_id=delivery_id, current_status=current_status)

########################################
# BELOW IS NEW DRIVER LOGIC
########################################

def driver_required(f):
    """
    A decorator ensuring only a logged-in user with role='driver' 
    can access the driver routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'driver':
            flash("Driver privileges required.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

########################################
# 3) DRIVER HOME
########################################
@delivery_bp.route('/driver_home')
@driver_required
def driver_home():
    """
    Shows all deliveries assigned to this driver 
    that are NOT yet 'Delivered', in descending order.
    Next to each, there's a button to "Start Order" (if status < 'pick up confirmed')
    or "Continue Order" (if status == 'pick up confirmed'), 
    which leads to the map view.
    """
    driver_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT d.id, d.purchase_id, d.status, d.address
            FROM deliveries d
            WHERE d.driver_id = ?
              AND d.status != 'Delivered'
            ORDER BY d.id DESC
        """, (driver_id,))
        deliveries = c.fetchall()

    return render_template('driver_home.html', deliveries=deliveries)

########################################
# 4) START/CONTINUE ORDER
########################################
@delivery_bp.route('/start_delivery/<int:delivery_id>', methods=['POST'])
@driver_required
def start_delivery(delivery_id):
    """
    If status is 'Pending' or 'Driver Assigned', update to 'pick up confirmed'.
    If status is already 'pick up confirmed', do nothing special except proceed.
    Then redirect to the map view.
    """
    driver_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT status 
            FROM deliveries
            WHERE id=? AND driver_id=?
        """, (delivery_id, driver_id))
        row = c.fetchone()
        if not row:
            flash("Delivery not found or not assigned to you.")
            return redirect(url_for('delivery_bp.driver_home'))

        current_status = row[0]
        if current_status in ('Pending', 'Driver Assigned'):
            c.execute("""
                UPDATE deliveries
                SET status='pick up confirmed'
                WHERE id=?
            """, (delivery_id,))
            conn.commit()
            flash("Order started (Pick Up Confirmed).")
        elif current_status == 'pick up confirmed':
            flash("Continuing order (already pick up confirmed).")
        else:
            flash("Cannot start or continue from current status.")

    return redirect(url_for('delivery_bp.view_map', delivery_id=delivery_id))

########################################
# 5) VIEW MAP (Driver side)
########################################
@delivery_bp.route('/view_map/<int:delivery_id>')
@driver_required
def view_map(delivery_id):
    """
    Displays a map with route from point A (fixed address) 
    to the delivery's address (point B).
    Also has a "Mark as Complete" button 
    if status == 'pick up confirmed'.
    """
    driver_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT status, address
            FROM deliveries
            WHERE id=? AND driver_id=?
        """, (delivery_id, driver_id))
        row = c.fetchone()
        if not row:
            flash("Delivery not found or not assigned to you.")
            return redirect(url_for('delivery_bp.driver_home'))

        status, address = row

    return render_template('driver_map.html',
                           delivery_id=delivery_id,
                           status=status,
                           address=address)

########################################
# 6) MARK AS COMPLETE
########################################
@delivery_bp.route('/complete_delivery/<int:delivery_id>', methods=['POST'])
@driver_required
def complete_delivery(delivery_id):
    """
    Sets status='Delivered' + delivered_date=NOW 
    if current status == 'pick up confirmed'.
    """
    driver_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT status
            FROM deliveries
            WHERE id=? AND driver_id=?
        """, (delivery_id, driver_id))
        row = c.fetchone()
        if not row:
            flash("Delivery not found or not assigned to you.")
            return redirect(url_for('delivery_bp.driver_home'))

        current_status = row[0]
        if current_status == 'pick up confirmed':
            c.execute("""
                UPDATE deliveries
                SET status='Delivered', delivered_date=CURRENT_TIMESTAMP
                WHERE id=?
            """, (delivery_id,))
            conn.commit()
            flash("Delivery marked as complete (Delivered).")
        else:
            flash("Cannot complete from current status.")

    return redirect(url_for('delivery_bp.driver_home'))

########################################
# BELOW IS NEW STAFF LOGIC
########################################

def staff_required(f):
    """
    A decorator ensuring only a logged-in user with role in ['staff','admin'] 
    can access staff routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login_bp.login'))

        role = session.get('role')
        if role not in ('staff', 'admin'):
            flash("Staff privileges required.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

########################################
# 7) PENDING DELIVERIES (Staff side)
########################################
@delivery_bp.route('/pending_deliveries')
@staff_required
def pending_deliveries():
    """
    Staff can view all deliveries where status='Pending' (no driver assigned yet).
    Lists them in descending order by ID.
    """
    with create_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, purchase_id, status, address
            FROM deliveries
            WHERE status='Pending'
            ORDER BY id DESC
        """)
        pending_list = c.fetchall()

    return render_template('pending_deliveries.html', pending_list=pending_list)

########################################
# 8) VIEW A SINGLE PENDING DELIVERY (Staff)
########################################
@delivery_bp.route('/view_pending/<int:delivery_id>')
@staff_required
def view_pending_delivery(delivery_id):
    """
    Staff can see the purchased items for this delivery's purchase_id
    and a form to assign a driver. 
    Only if the delivery is still 'Pending'.
    """
    with create_connection() as conn:
        c = conn.cursor()
        # fetch the delivery
        c.execute("""
            SELECT purchase_id, status, address
            FROM deliveries
            WHERE id=?
        """, (delivery_id,))
        row = c.fetchone()
        if not row:
            flash("Delivery not found.")
            return redirect(url_for('delivery_bp.pending_deliveries'))

        purchase_id, status, address = row
        if status != 'Pending':
            flash("This delivery is not pending or has already been assigned.")
            return redirect(url_for('delivery_bp.pending_deliveries'))

        # fetch all items from purchase_items + books
        c.execute("""
            SELECT b.cover_image, b.title, pi.quantity
            FROM purchase_items pi
            JOIN books b ON pi.book_id = b.id
            WHERE pi.purchase_id=?
        """, (purchase_id,))
        items = c.fetchall()

        # fetch the drivers (for the dropdown)
        c.execute("""
            SELECT d.id, u.email
            FROM drivers d
            JOIN users u ON d.user_id = u.id
        """)
        drivers = c.fetchall()

    return render_template('view_pending_delivery.html',
                           delivery_id=delivery_id,
                           purchase_id=purchase_id,
                           address=address,
                           items=items,
                           drivers=drivers)

########################################
# 9) ASSIGN DRIVER (Staff)
########################################
@delivery_bp.route('/assign_driver/<int:delivery_id>', methods=['POST'])
@staff_required
def assign_driver(delivery_id):
    """
    Staff chooses a driver from the dropdown. 
    We update deliveries.driver_id=? and status='Driver Assigned'.
    """
    driver_id = request.form.get('driver_id')
    if not driver_id:
        flash("Please select a driver.")
        return redirect(url_for('delivery_bp.view_pending_delivery', delivery_id=delivery_id))

    with create_connection() as conn:
        c = conn.cursor()
        # double-check if it's still pending
        c.execute("""
            SELECT status
            FROM deliveries
            WHERE id=?
        """, (delivery_id,))
        row = c.fetchone()
        if not row:
            flash("Delivery not found.")
            return redirect(url_for('delivery_bp.pending_deliveries'))

        status = row[0]
        if status != 'Pending':
            flash("Delivery is not pending. Can't assign driver.")
            return redirect(url_for('delivery_bp.pending_deliveries'))

        # assign driver
        c.execute("""
            UPDATE deliveries
            SET driver_id=?, status='Driver Assigned'
            WHERE id=?
        """, (driver_id, delivery_id))
        conn.commit()

    flash("Driver assigned successfully!")
    return redirect(url_for('delivery_bp.pending_deliveries'))
