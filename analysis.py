# analysis.py

import sqlite3
from flask import Blueprint, render_template, session, redirect, url_for, flash
from functools import wraps

analysis_bp = Blueprint('analysis_bp', __name__)
DATABASE = 'bookstore.db'

def create_connection():
    return sqlite3.connect(DATABASE)

def staff_required(f):
    """
    Decorator ensuring only staff or admin can access these routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in.")
            return redirect(url_for('login_bp.login'))

        role = session.get('role')
        if role not in ('staff', 'admin'):
            flash("Staff or admin privileges required.")
            return redirect(url_for('login_bp.login'))

        return f(*args, **kwargs)
    return decorated_function

@analysis_bp.route('/sales_analysis')
@staff_required
def sales_analysis():
    """
    Shows graphs/charts for daily sales, total revenue, and most purchased books.
    """
    # Query daily sales from 'purchases'
    # We'll group by date(payment_date) and sum payment_amount
    with create_connection() as conn:
        cursor = conn.cursor()

        # 1) Daily Sales (line chart)
        cursor.execute("""
            SELECT strftime('%Y-%m-%d', payment_date) AS day, 
                   SUM(payment_amount) AS total
            FROM purchases
            GROUP BY strftime('%Y-%m-%d', payment_date)
            ORDER BY day
        """)
        daily_rows = cursor.fetchall()
        # daily_rows => [(day, total), (day, total), ...]

        # 2) Most Purchased Books (bar chart)
        cursor.execute("""
            SELECT b.title, SUM(pi.quantity) AS total_qty
            FROM purchase_items pi
            JOIN books b ON pi.book_id = b.id
            GROUP BY b.id
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        most_bought_rows = cursor.fetchall()
        # most_bought_rows => [(title, total_qty), (title, total_qty), ...]

        # 3) Total Revenue (simple sum)
        cursor.execute("""
            SELECT SUM(payment_amount) FROM purchases
        """)
        total_revenue_row = cursor.fetchone()
        total_revenue = total_revenue_row[0] if total_revenue_row[0] else 0.0

    # We'll pass these to the template
    return render_template('analysis.html',
                           daily_rows=daily_rows,
                           most_bought_rows=most_bought_rows,
                           total_revenue=total_revenue)
