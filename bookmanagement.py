# bookmanagement.py

import sqlite3, base64
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from functools import wraps

book_bp = Blueprint('book_bp', __name__)
DATABASE = 'bookstore.db'

def create_connection():
    """Helper to connect to SQLite DB."""
    conn = sqlite3.connect(DATABASE)
    return conn

########################################
# STAFF-REQUIRED DECORATOR
########################################
def staff_required(f):
    """
    Decorator ensuring only staff or admin can access these routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in.")
            return redirect(url_for('login_bp.login'))

        role = session.get('role')
        if role not in ('staff', 'admin'):
            flash("Staff or admin privileges required.")
            return redirect(url_for('login_bp.login'))

        return f(*args, **kwargs)
    return decorated_function

########################################
# JINJA FILTER: Base64 encoding for BLOB
########################################
@book_bp.app_template_filter('b64encode')
def b64encode_filter(binary_data):
    """
    Converts BLOB bytes to a Base64 string for embedding in <img>.
    """
    if binary_data is None:
        return ''
    return base64.b64encode(binary_data).decode('utf-8')

########################################
# 1) ADD NEW BOOK
########################################
@book_bp.route('/add_book', methods=['GET', 'POST'])
@staff_required
def add_book():
    """
    Staff can add a new book. 
    Must upload cover image and PDF (both stored as BLOB).
    Also stores 'condition' and 'quantity'.
    """
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        description = request.form['description']
        category = request.form['category']
        price = request.form['price']
        condition = request.form['condition']
        quantity = request.form['quantity']

        # Validate required fields
        if not (title and author and price and quantity):
            flash("Title, Author, Price, and Quantity are required.")
            return redirect(url_for('book_bp.add_book'))

        # Validate file fields
        cover_file = request.files.get('cover_image')
        pdf_file = request.files.get('pdf_file')

        if not cover_file or not pdf_file:
            flash("Cover image and PDF file are required.")
            return redirect(url_for('book_bp.add_book'))

        cover_bytes = cover_file.read()
        pdf_bytes = pdf_file.read()

        # Insert into DB
        with create_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO books 
                    (title, author, description, category, price, cover_image, pdf_file, condition, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, author, description, category, price, cover_bytes, pdf_bytes, condition, quantity))

                conn.commit()
                flash("New book added successfully!")
            except Exception as e:
                conn.rollback()
                flash(f"Error adding book: {e}")
                return redirect(url_for('book_bp.add_book'))

        return redirect(url_for('book_bp.manage_books'))

    return render_template('add_book.html')

########################################
# 2) MANAGE BOOKS (Default View)
########################################
@book_bp.route('/manage_books', methods=['GET'])
@staff_required
def manage_books():
    """
    Displays all books in a table. 
    Each row has an Edit button to modify details.
    """
    with create_connection() as conn:
        cursor = conn.cursor()
        # Now include 'quantity' in the query
        cursor.execute("""
            SELECT id, title, author, category, price, cover_image, quantity
            FROM books
        """)
        books = cursor.fetchall()

    return render_template('manage_books.html', books=books)

########################################
# 3) EDIT BOOK (EXCEPT PDF)
########################################
@book_bp.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@staff_required
def edit_book(book_id):
    """
    Allows staff to update book details (title, author, desc, category, price, condition, quantity)
    and optionally replace the cover image. PDF is NOT updatable.
    """
    with create_connection() as conn:
        cursor = conn.cursor()

        # Fetch existing record
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        book = cursor.fetchone()
        if not book:
            flash("Book not found.")
            return redirect(url_for('book_bp.manage_books'))

        # book columns => 
        # (id=0, title=1, author=2, description=3, category=4, price=5,
        #  cover_image=6, pdf_file=7, created_at=8, condition=9, quantity=10)
        # Adjust indices if your DB differs.

        if request.method == 'POST':
            title = request.form['title']
            author = request.form['author']
            description = request.form['description']
            category = request.form['category']
            price = request.form['price']
            condition = request.form['condition']
            quantity = request.form['quantity']

            if not (title and author and price and quantity):
                flash("Title, Author, Price, and Quantity are required.")
                return redirect(url_for('book_bp.edit_book', book_id=book_id))

            cover_file = request.files.get('cover_image')
            cover_bytes = None
            if cover_file and cover_file.filename:
                cover_bytes = cover_file.read()

            try:
                with create_connection() as conn2:
                    cursor2 = conn2.cursor()
                    if cover_bytes:
                        cursor2.execute("""
                            UPDATE books
                            SET title=?, author=?, description=?, category=?, price=?, cover_image=?, condition=?, quantity=?
                            WHERE id=?
                        """, (title, author, description, category, price, cover_bytes, condition, quantity, book_id))
                    else:
                        cursor2.execute("""
                            UPDATE books
                            SET title=?, author=?, description=?, category=?, price=?, condition=?, quantity=?
                            WHERE id=?
                        """, (title, author, description, category, price, condition, quantity, book_id))

                    conn2.commit()
                flash("Book updated successfully!")
            except Exception as e:
                flash(f"Error updating book: {e}")

            return redirect(url_for('book_bp.manage_books'))

        return render_template('edit_book.html', book=book)

########################################
# 4) LIVE SEARCH ENDPOINT
########################################
@book_bp.route('/search_books', methods=['GET'])
@staff_required
def search_books():
    """
    Returns JSON of books matching the query (case-insensitive).
    We also Base64-encode the cover image so we can display it in the front-end.
    Now includes 'quantity'.
    """
    query = request.args.get('q', '').strip()
    query_lower = query.lower()

    wildcard = f"%{query_lower}%"
    with create_connection() as conn:
        cursor = conn.cursor()
        # Include quantity in the query
        cursor.execute("""
            SELECT id, title, author, category, price, cover_image, quantity
            FROM books
            WHERE lower(title) LIKE ?
               OR lower(author) LIKE ?
               OR lower(category) LIKE ?
        """, (wildcard, wildcard, wildcard))
        results = cursor.fetchall()

    data = []
    for row in results:
        # row => (id, title, author, category, price, cover_image, quantity)
        book_id = row[0]
        title = row[1]
        author = row[2]
        category = row[3]
        price = row[4]
        cover_blob = row[5]
        quantity = row[6]

        cover_b64 = ''
        if cover_blob:
            cover_b64 = base64.b64encode(cover_blob).decode('utf-8')

        data.append({
            'id': book_id,
            'title': title,
            'author': author,
            'category': category,
            'price': price,
            'cover_image': cover_b64,
            'quantity': quantity
        })

    return jsonify(data)
