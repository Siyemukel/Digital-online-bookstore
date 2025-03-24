import sqlite3, base64
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps

user_bp = Blueprint('user_bp', __name__)
DATABASE = 'bookstore.db'

def create_connection():
    return sqlite3.connect(DATABASE)

def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


@user_bp.app_template_filter('b64encode')
def b64encode_filter(binary_data):
    if binary_data is None:
        return ''
    return base64.b64encode(binary_data).decode('utf-8')

@user_bp.route('/user_home')
@user_required
def user_home():
    """
    Displays:
      - Latest Books (top 5 newest by id desc)
      - Popular Books (top 5 by sum of purchase_items.quantity)
      - Recommended Books (top 5 from categories user purchased the most).
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, price, cover_image, quantity, condition
            FROM books
            ORDER BY id DESC
            LIMIT 5
        """)
        latest_books = cursor.fetchall()

        cursor.execute("""
            SELECT b.id, b.title, b.price, b.cover_image, b.quantity, b.condition,
                   COALESCE(SUM(pi.quantity), 0) as total_qty
            FROM books b
            LEFT JOIN purchase_items pi ON pi.book_id = b.id
            GROUP BY b.id
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        popular_books = cursor.fetchall()

        recommended_books = []
        cursor.execute("""
            SELECT b.category, SUM(pi.quantity) AS cat_qty
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ?
            GROUP BY b.category
            ORDER BY cat_qty DESC
        """, (user_id,))
        cat_rows = cursor.fetchall() 
        purchased_cats = [row[0] for row in cat_rows]

        if purchased_cats:
            for (cat, cat_qty) in cat_rows:
                needed = 5 - len(recommended_books)
                if needed <= 0:
                    break
                cursor.execute("""
                    SELECT id, title, price, cover_image, quantity, condition
                    FROM books
                    WHERE category=?
                    ORDER BY id DESC
                    LIMIT ?
                """, (cat, needed))
                partial = cursor.fetchall()
                recommended_books.extend(partial)

            needed = 5 - len(recommended_books)
            if needed > 0:
                placeholders = ",".join("?" for _ in purchased_cats)
                if purchased_cats:
                    query_others = f"""
                        SELECT id, title, price, cover_image, quantity, condition
                        FROM books
                        WHERE category NOT IN ({placeholders})
                        ORDER BY id DESC
                        LIMIT ?
                    """
                    cursor.execute(query_others, (*purchased_cats, needed))
                else:
                    query_others = """
                        SELECT id, title, price, cover_image, quantity, condition
                        FROM books
                        ORDER BY id DESC
                        LIMIT ?
                    """
                    cursor.execute(query_others, (needed,))
                leftover = cursor.fetchall()
                recommended_books.extend(leftover)

        has_categories = bool(purchased_cats)

    return render_template('user_home.html',
                           latest_books=latest_books,
                           popular_books=popular_books,
                           recommended_books=recommended_books,
                           has_categories=has_categories)

@user_bp.route('/user_home2')
@user_required
def user_home2():
    """
    Second home page route, returning user_home2.html.
    We'll fetch ALL data for each category, then take only top 5 in Python.
    This is just to see if images appear or not with a different approach.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        c = conn.cursor()

        c.execute("""
            SELECT id, title, price, cover_image, quantity, condition
            FROM books
            ORDER BY id DESC
        """)
        latest_all = c.fetchall()
        latest_top5 = latest_all[:5]

        c.execute("""
            SELECT b.id, b.title, b.price, b.cover_image, b.quantity, b.condition,
                   COALESCE(SUM(pi.quantity), 0) AS total_qty
            FROM books b
            LEFT JOIN purchase_items pi ON pi.book_id = b.id
            GROUP BY b.id
            ORDER BY total_qty DESC
        """)
        popular_all = c.fetchall()
        popular_top5 = popular_all[:5]

        c.execute("""
            SELECT DISTINCT pi.book_id
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            WHERE p.user_id=?
        """, (user_id,))
        owned_rows = c.fetchall()
        owned_ids = [r[0] for r in owned_rows] if owned_rows else []

        rec_list = []
        for row in popular_all:
            if row[0] not in owned_ids:
                rec_list.append(row)
        recommended_top5 = rec_list[:5]

    return render_template('user_home2.html',
                           latest_top5=latest_top5,
                           popular_top5=popular_top5,
                           recommended_top5=recommended_top5
    )

@user_bp.route('/all_books')
@user_required
def all_books():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, price, cover_image, quantity, condition
            FROM books
            ORDER BY id DESC
        """)
        books = cursor.fetchall()
    return render_template('all_books.html', books=books)

@user_bp.route('/popular_books')
@user_required
def popular_books():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.title, b.price, b.cover_image, b.quantity, b.condition,
                   COALESCE(SUM(pi.quantity), 0) AS total_qty
            FROM books b
            LEFT JOIN purchase_items pi ON pi.book_id = b.id
            GROUP BY b.id
            ORDER BY total_qty DESC
        """)
        books = cursor.fetchall()
    return render_template('popular_books.html', books=books)


@user_bp.route('/recommended_books')
@user_required
def recommended_books():
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT b.category, SUM(pi.quantity) AS cat_qty
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            JOIN books b ON pi.book_id = b.id
            WHERE p.user_id = ?
            GROUP BY b.category
            ORDER BY cat_qty DESC
        """, (user_id,))
        cat_rows = cursor.fetchall()
        purchased_cats = [row[0] for row in cat_rows]

        full_list = []
        for (cat, cat_qty) in cat_rows:
            cursor.execute("""
                SELECT id, title, price, cover_image, quantity, condition
                FROM books
                WHERE category=?
                ORDER BY id DESC
            """, (cat,))
            cat_books = cursor.fetchall()
            full_list.extend(cat_books)

        if purchased_cats:
            placeholders = ",".join("?" for _ in purchased_cats)
            query_others = f"""
                SELECT id, title, price, cover_image, quantity, condition
                FROM books
                WHERE category NOT IN ({placeholders})
                ORDER BY id DESC
            """
            cursor.execute(query_others, purchased_cats)
            other_books = cursor.fetchall()
            full_list.extend(other_books)
        else:
            cursor.execute("""
                SELECT id, title, price, cover_image, quantity, condition
                FROM books
                ORDER BY id DESC
            """)
            full_list = cursor.fetchall()

        has_categories = bool(purchased_cats)

    return render_template('recommended_books.html', books=full_list, user_categories=purchased_cats, has_categories=has_categories)


@user_bp.route('/book_details/<int:book_id>')
@user_required
def book_details(book_id):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, author, description, category, price, cover_image, quantity, condition
            FROM books
            WHERE id=?
        """, (book_id,))
        book = cursor.fetchone()
        if not book:
            flash("Book not found.")
            return redirect(url_for('user_bp.all_books'))

        cursor.execute("""
            SELECT r.id, r.rating, r.comment, r.created_at, u.email, pp.pic
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            LEFT JOIN profile_pics pp ON pp.user_id = u.id
            WHERE r.book_id=?
            ORDER BY r.created_at DESC
        """, (book_id,))
        reviews = cursor.fetchall()

    return render_template('book_details.html', book=book, reviews=reviews)

@user_bp.route('/add_to_cart/<int:book_id>', methods=['POST'])
@user_required
def add_to_cart(book_id):
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM books WHERE id=?", (book_id,))
        row = cursor.fetchone()
        if not row:
            flash("Book does not exist.")
            return redirect(url_for('user_bp.user_home'))
        book_stock = row[0]
        if book_stock <= 0:
            flash("No copies available.")
            return redirect(url_for('user_bp.user_home'))

        cursor.execute("SELECT id FROM cart WHERE user_id=?", (user_id,))
        cart_row = cursor.fetchone()
        if cart_row:
            cart_id = cart_row[0]
        else:
            cursor.execute("INSERT INTO cart(user_id) VALUES(?)", (user_id,))
            cart_id = cursor.lastrowid

        cursor.execute("""
            SELECT id, quantity
            FROM cart_items
            WHERE cart_id=? AND book_id=?
        """, (cart_id, book_id))
        existing_item = cursor.fetchone()
        if existing_item:
            cart_item_id, current_qty = existing_item
            new_qty = current_qty + 1
            if new_qty > book_stock:
                flash("You cannot add more than available copies.")
            else:
                cursor.execute("""
                    UPDATE cart_items
                    SET quantity=?
                    WHERE id=?
                """, (new_qty, cart_item_id))
                flash("Increased quantity by 1.")
        else:
            if book_stock < 1:
                flash("No copies available.")
            else:
                cursor.execute("""
                    INSERT INTO cart_items(cart_id, book_id, quantity)
                    VALUES(?, ?, ?)
                """, (cart_id, book_id, 1))
                flash("Book added to cart.")
        conn.commit()

    return redirect(request.referrer or url_for('user_bp.user_home'))

@user_bp.route('/search_user_books')
@user_required
def search_user_books():
    query = request.args.get('q', '').strip().lower()
    scope = request.args.get('scope', 'all')
    wildcard = f"%{query}%"

    with create_connection() as conn:
        cursor = conn.cursor()

        if scope == 'popular':
            base_sql = """
                SELECT b.id, b.title, b.price, b.cover_image, 
                       COALESCE(SUM(pi.quantity), 0) AS total_qty
                FROM books b
                LEFT JOIN purchase_items pi ON pi.book_id = b.id
                WHERE lower(b.title) LIKE ?
                GROUP BY b.id
                ORDER BY total_qty DESC
            """
            cursor.execute(base_sql, (wildcard,))
            results = cursor.fetchall()
            data = []
            for row in results:
                data.append({
                    'id': row[0],
                    'title': row[1],
                    'price': row[2],
                    'cover_image': base64.b64encode(row[3]).decode('utf-8') if row[3] else ''
                })
            return jsonify(data)

        elif scope == 'all':
            base_sql = """
                SELECT id, title, price, cover_image
                FROM books
                WHERE lower(title) LIKE ?
                ORDER BY id DESC
            """
            cursor.execute(base_sql, (wildcard,))
            results = cursor.fetchall()

        else: 
            base_sql = """
                SELECT id, title, price, cover_image
                FROM books
                WHERE lower(title) LIKE ?
                ORDER BY id DESC
            """
            cursor.execute(base_sql, (wildcard,))
            results = cursor.fetchall()

    data = []
    for row in results:
        data.append({
            'id': row[0],
            'title': row[1],
            'price': row[2],
            'cover_image': base64.b64encode(row[3]).decode('utf-8') if row[3] else ''
        })

    return jsonify(data)


@user_bp.route('/my_profile', methods=['GET', 'POST'])
@user_required
def my_profile():
    """
    Allows user to update personal details (in 'students'),
    optionally change password, and upload a profile pic.
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT email, password FROM users WHERE id=?", (user_id,))
        user_row = cursor.fetchone()
        user_email = user_row[0] if user_row else ''
        
        cursor.execute("""
            SELECT first_name, last_name, phone
            FROM students
            WHERE user_id=?
        """, (user_id,))
        student_row = cursor.fetchone()
        first_name = student_row[0] if student_row else ''
        last_name = student_row[1] if student_row else ''
        phone = student_row[2] if student_row else ''

        cursor.execute("SELECT pic FROM profile_pics WHERE user_id=?", (user_id,))
        pic_row = cursor.fetchone()
        profile_pic = pic_row[0] if pic_row else None

        if request.method == 'POST':
            new_first = request.form.get('first_name')
            new_last = request.form.get('last_name')
            new_phone = request.form.get('phone')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            pic_file = request.files.get('profile_pic')

            cursor.execute("""
                UPDATE students
                SET first_name=?, last_name=?, phone=?
                WHERE user_id=?
            """, (new_first, new_last, new_phone, user_id))

            if new_password:
                if new_password != confirm_password:
                    flash("New password and Confirm password do not match.")
                    conn.rollback()
                    return redirect(url_for('user_bp.my_profile'))
                else:
                    cursor.execute("""
                        UPDATE users
                        SET password=?
                        WHERE id=?
                    """, (new_password, user_id))

            if pic_file and pic_file.filename:
                pic_bytes = pic_file.read()
                if pic_row:
                    cursor.execute("""
                        UPDATE profile_pics
                        SET pic=?
                        WHERE user_id=?
                    """, (pic_bytes, user_id))
                else:
                    cursor.execute("""
                        INSERT INTO profile_pics(user_id, pic)
                        VALUES(?, ?)
                    """, (user_id, pic_bytes))

            conn.commit()
            flash("Profile updated successfully!")
            return redirect(url_for('user_bp.my_profile'))

        profile_pic_b64 = None
        if profile_pic:
            profile_pic_b64 = base64.b64encode(profile_pic).decode('utf-8')

        return render_template('my_profile.html',
                               email=user_email,
                               first_name=first_name,
                               last_name=last_name,
                               phone=phone,
                               profile_pic_b64=profile_pic_b64)
