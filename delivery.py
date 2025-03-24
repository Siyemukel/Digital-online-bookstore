
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

@delivery_bp.route('/my_deliveries')
@user_required
def my_deliveries():
    
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

def driver_required(f):
  
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'driver':
            flash("Driver privileges required.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

@delivery_bp.route('/driver_home')
@driver_required
def driver_home():
   
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


@delivery_bp.route('/start_delivery/<int:delivery_id>', methods=['POST'])
@driver_required
def start_delivery(delivery_id):
    
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


@delivery_bp.route('/view_map/<int:delivery_id>')
@driver_required
def view_map(delivery_id):
   
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

@delivery_bp.route('/complete_delivery/<int:delivery_id>', methods=['POST'])
@driver_required
def complete_delivery(delivery_id):
  
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

def staff_required(f):
  
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

@delivery_bp.route('/pending_deliveries')
@staff_required
def pending_deliveries():
   
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


@delivery_bp.route('/view_pending/<int:delivery_id>')
@staff_required
def view_pending_delivery(delivery_id):
  
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
