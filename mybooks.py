# mybooks.py

import sqlite3, base64
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, make_response
from functools import wraps
import datetime

mybooks_bp = Blueprint('mybooks_bp', __name__)
DATABASE = 'bookstore.db'

def create_connection():
    return sqlite3.connect(DATABASE)

########################################
# Decorator ensuring a user is logged in
########################################
def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

########################################
# 1) MY BOOKS (LIST)
########################################
@mybooks_bp.route('/my_books')
@user_required
def my_books():
    """
    Displays all distinct books the user has purchased (past or current).
    If user bought the same book multiple times, show it once.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        # Distinct book IDs from purchase_items + purchases
        cursor.execute("""
            SELECT DISTINCT b.id, b.title, b.author, b.cover_image
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ?
        """, (user_id,))
        purchased_books = cursor.fetchall()
    return render_template('my_books.html', purchased_books=purchased_books)

########################################
# 2) BOOK DETAILS (FOR PURCHASED BOOK)
########################################
@mybooks_bp.route('/my_books/book_details/<int:book_id>')
@user_required
def purchased_book_details(book_id):
    """
    Shows details of a purchased book:
      - Add to favorites
      - Leave a review
      - Link to read PDF inline

    SQL returns columns in this order:
      (id=0, title=1, author=2, description=3, category=4, price=5, cover_image=6)
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        # Verify the user actually purchased this book
        cursor.execute("""
            SELECT b.id, b.title, b.author, b.description, b.category, b.price, b.cover_image
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ? AND b.id = ?
            LIMIT 1
        """, (user_id, book_id))
        book = cursor.fetchone()

        if not book:
            flash("You haven't purchased this book.")
            return redirect(url_for('mybooks_bp.my_books'))

    return render_template('purchased_book_details.html', book=book)

########################################
# 3) ADD TO FAVORITES
########################################
@mybooks_bp.route('/my_books/add_favorite/<int:book_id>', methods=['POST'])
@user_required
def add_favorite(book_id):
    """
    Adds a book to the user's favorites (table: favorites).
    If already in favorites, flash an error.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        # Check if already favorited
        cursor.execute("""
            SELECT id FROM favorites
            WHERE user_id=? AND book_id=?
        """, (user_id, book_id))
        row = cursor.fetchone()
        if row:
            flash("This book is already in your favorites.")
        else:
            # Insert
            cursor.execute("""
                INSERT INTO favorites(user_id, book_id)
                VALUES(?, ?)
            """, (user_id, book_id))
            flash("Book added to favorites.")

        conn.commit()

    return redirect(request.referrer or url_for('mybooks_bp.my_books'))

########################################
# 4) LEAVE A REVIEW
########################################
@mybooks_bp.route('/my_books/leave_review/<int:book_id>', methods=['GET', 'POST'])
@user_required
def leave_review(book_id):
    """
    GET => shows a form for rating & comment
    POST => inserts into reviews table
    """
    user_id = session['user_id']

    # Verify user purchased this book
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ? AND b.id = ?
            LIMIT 1
        """, (user_id, book_id))
        owned = cursor.fetchone()
        if not owned:
            flash("You haven't purchased this book, can't leave a review.")
            return redirect(url_for('mybooks_bp.my_books'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment', '').strip()

        if not rating:
            flash("Please provide a rating.")
            return redirect(url_for('mybooks_bp.leave_review', book_id=book_id))

        # Insert into reviews
        with create_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reviews(user_id, book_id, rating, comment)
                VALUES(?, ?, ?, ?)
            """, (user_id, book_id, rating, comment))
            conn.commit()

        flash("Review submitted!")
        return redirect(url_for('mybooks_bp.book_details_for_redirect', book_id=book_id))

    # GET => show a form
    return render_template('leave_review.html', book_id=book_id)

# A small helper route to redirect after review submission
@mybooks_bp.route('/my_books/book_redirect/<int:book_id>')
def book_details_for_redirect(book_id):
    # Just redirect to the purchased book details
    return redirect(url_for('mybooks_bp.purchased_book_details', book_id=book_id))

########################################
# 5) READ PDF (EMBEDDED, NOT DOWNLOADABLE)
########################################
@mybooks_bp.route('/my_books/read_pdf/<int:book_id>')
@user_required
def read_pdf(book_id):
    """
    Displays the PDF in an <iframe> so the user can read it inline.
    We can't fully block downloads or screenshots, but we won't set content-disposition=attachment.
    """
    user_id = session['user_id']
    # Verify user purchased
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.pdf_file
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ? AND b.id = ?
            LIMIT 1
        """, (user_id, book_id))
        row = cursor.fetchone()
        if not row:
            flash("You haven't purchased this book or no PDF found.")
            return redirect(url_for('mybooks_bp.my_books'))

        pdf_data = row[0]
        if not pdf_data:
            flash("No PDF available for this book.")
            return redirect(url_for('mybooks_bp.my_books'))

    return render_template('pdf_reader.html', book_id=book_id)

@mybooks_bp.route('/my_books/get_pdf_data/<int:book_id>')
@user_required
def get_pdf_data(book_id):
    """
    Serves the PDF with inline content-disposition.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.pdf_file
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ? AND b.id = ?
            LIMIT 1
        """, (user_id, book_id))
        row = cursor.fetchone()
        if not row or not row[0]:
            flash("No PDF available.")
            return redirect(url_for('mybooks_bp.my_books'))

        pdf_data = row[0]

    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    # inline => opens in browser; no forced download
    response.headers['Content-Disposition'] = 'inline; filename="book.pdf"'
    return response

########################################
# 6) MY FAVORITES
########################################
@mybooks_bp.route('/my_books/my_favorites')
@user_required
def my_favorites():
    """
    Shows all books user has favorited.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.title, b.author, b.cover_image
            FROM favorites f
            JOIN books b ON f.book_id = b.id
            WHERE f.user_id = ?
        """, (user_id,))
        fav_books = cursor.fetchall()

    return render_template('my_favorites.html', fav_books=fav_books)
