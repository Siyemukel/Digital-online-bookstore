import sqlite3, os, requests, base64
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
import datetime

cart_bp = Blueprint('cart_bp', __name__)
DATABASE = 'bookstore.db'

# PayPal config
PAYPAL_MODE = "sandbox"  # or "live"
PAYPAL_CLIENT_ID = "AZ3yoF8lLOdoQgb9895WkDKJsUZc4R7wXld2p_tZukhvJUjgTYg901G83GfAiN0BMet_P874dOemnb6s"
PAYPAL_CLIENT_SECRET = "EBLvhafwxBdX2i8J0HFT76uft1tUC_ql0yz_YGvp0Ars7BUbn15rrDssBjxIGi2BO3S239e8v5xCyjUJ"

DELIVERY_FEE = 30.0  # R30 for delivery

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


@cart_bp.route('/cart')
@user_required
def view_cart():
    """
    Displays items in the user's cart, plus total cost.
    Shows radio buttons for pickup/delivery, 
    which is saved in session['delivery_method'].
    """
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cart WHERE user_id=?", (user_id,))
        cart_row = cursor.fetchone()
        if not cart_row:
            return render_template('cart.html', items=[], total=0, delivery_method='pickup')

        cart_id = cart_row[0]
        cursor.execute("""
            SELECT ci.id, b.id AS book_id, b.title, b.price, b.cover_image, ci.quantity, b.quantity AS stock
            FROM cart_items ci
            JOIN books b ON ci.book_id = b.id
            WHERE ci.cart_id=?
        """, (cart_id,))
        items = cursor.fetchall()

        total = 0
        for item in items:
            price = item[3]
            qty_in_cart = item[5]
            total += (price * qty_in_cart)

    delivery_method = session.get('delivery_method', 'pickup')
    return render_template('cart.html', items=items, total=total, delivery_method=delivery_method)

@cart_bp.route('/increase_quantity/<int:cart_item_id>', methods=['POST'])
@user_required
def increase_quantity(cart_item_id):
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cart_id, book_id, quantity
            FROM cart_items
            WHERE id=?
        """, (cart_item_id,))
        row = cursor.fetchone()
        if not row:
            flash("Cart item not found.")
            return redirect(url_for('cart_bp.view_cart'))

        cart_id, book_id, current_qty = row

        cursor.execute("SELECT user_id FROM cart WHERE id=?", (cart_id,))
        cart_owner = cursor.fetchone()
        if not cart_owner or cart_owner[0] != user_id:
            flash("Unauthorized action.")
            return redirect(url_for('cart_bp.view_cart'))

        cursor.execute("SELECT quantity FROM books WHERE id=?", (book_id,))
        stock_row = cursor.fetchone()
        if not stock_row:
            flash("Book not found.")
            return redirect(url_for('cart_bp.view_cart'))

        stock = stock_row[0]
        new_qty = current_qty + 1
        if new_qty > stock:
            flash("Cannot exceed available stock.")
        else:
            cursor.execute("""
                UPDATE cart_items
                SET quantity=?
                WHERE id=?
            """, (new_qty, cart_item_id))
            flash("Increased quantity by 1.")

        conn.commit()
    return redirect(url_for('cart_bp.view_cart'))


@cart_bp.route('/decrease_quantity/<int:cart_item_id>', methods=['POST'])
@user_required
def decrease_quantity(cart_item_id):
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cart_id, book_id, quantity
            FROM cart_items
            WHERE id=?
        """, (cart_item_id,))
        row = cursor.fetchone()
        if not row:
            flash("Cart item not found.")
            return redirect(url_for('cart_bp.view_cart'))

        cart_id, book_id, current_qty = row

        cursor.execute("SELECT user_id FROM cart WHERE id=?", (cart_id,))
        cart_owner = cursor.fetchone()
        if not cart_owner or cart_owner[0] != user_id:
            flash("Unauthorized action.")
            return redirect(url_for('cart_bp.view_cart'))

        new_qty = current_qty - 1
        if new_qty < 1:
            flash("Quantity cannot go below 1.")
        else:
            cursor.execute("""
                UPDATE cart_items
                SET quantity=?
                WHERE id=?
            """, (new_qty, cart_item_id))
            flash("Decreased quantity by 1.")

        conn.commit()
    return redirect(url_for('cart_bp.view_cart'))

@cart_bp.route('/remove_item/<int:cart_item_id>', methods=['POST'])
@user_required
def remove_item(cart_item_id):
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cart_id FROM cart_items WHERE id=?", (cart_item_id,))
        row = cursor.fetchone()
        if not row:
            flash("Item not found.")
            return redirect(url_for('cart_bp.view_cart'))

        cart_id = row[0]
        cursor.execute("SELECT user_id FROM cart WHERE id=?", (cart_id,))
        cart_owner = cursor.fetchone()
        if not cart_owner or cart_owner[0] != user_id:
            flash("Unauthorized removal.")
            return redirect(url_for('cart_bp.view_cart'))

        cursor.execute("DELETE FROM cart_items WHERE id=?", (cart_item_id,))
        conn.commit()
        flash("Item removed.")
    return redirect(url_for('cart_bp.view_cart'))

@cart_bp.route('/clear_cart', methods=['POST'])
@user_required
def clear_cart():
    user_id = session['user_id']
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cart WHERE user_id=?", (user_id,))
        cart_row = cursor.fetchone()
        if cart_row:
            c_id = cart_row[0]
            cursor.execute("DELETE FROM cart_items WHERE cart_id=?", (c_id,))
            conn.commit()
        flash("Cart cleared.")
    return redirect(url_for('cart_bp.view_cart'))


@cart_bp.route('/select_delivery_method', methods=['POST'])
@user_required
def select_delivery_method():
    """
    Called when user chooses 'pickup' or 'delivery' from the cart page.
    If 'delivery', redirect to /enter_address.
    If 'pickup', go directly to /checkout.
    """
    method = request.form.get('delivery_method', 'pickup')
    session['delivery_method'] = method

    if method == 'delivery':
        return redirect(url_for('cart_bp.enter_address'))
    else:
        # pickup
        return redirect(url_for('cart_bp.checkout'))

@cart_bp.route('/enter_address', methods=['GET', 'POST'])
@user_required
def enter_address():
    """
    If GET, shows a form with Google Maps autocomplete for the address.
    If POST, store the address in session and proceed to checkout.
    """
    if request.method == 'POST':
        address = request.form.get('address')
        if not address:
            flash("Please enter a delivery address.")
            return redirect(url_for('cart_bp.enter_address'))

        
        session['delivery_address'] = address
        return redirect(url_for('cart_bp.checkout'))

    # GET => show the address form
    return render_template('enter_address.html')


@cart_bp.route('/checkout', methods=['GET', 'POST'])
@user_required
def checkout():
    """
    Creates a PayPal payment and redirects user to PayPal for approval.
    If delivery_method='delivery', add R30 to total, require address from session.
    """
    user_id = session['user_id']

    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cart WHERE user_id=?", (user_id,))
        cart_row = cursor.fetchone()
        if not cart_row:
            flash("Your cart is empty.")
            return redirect(url_for('cart_bp.view_cart'))

        cart_id = cart_row[0]
        cursor.execute("""
            SELECT b.title, b.price, ci.quantity
            FROM cart_items ci
            JOIN books b ON ci.book_id = b.id
            WHERE ci.cart_id=?
        """, (cart_id,))
        items = cursor.fetchall()
        subtotal = sum(item[1] * item[2] for item in items)

    method = session.get('delivery_method', 'pickup')
    delivery_fee = 0.0
    address = None

    if method == 'delivery':
        address = session.get('delivery_address')
        if not address:
            flash("Please provide a delivery address.")
            return redirect(url_for('cart_bp.enter_address'))
        delivery_fee = DELIVERY_FEE

    total = subtotal + delivery_fee

    token_url = f"https://api.{ 'sandbox.' if PAYPAL_MODE=='sandbox' else '' }paypal.com/v1/oauth2/token"
    payment_url = f"https://api.{ 'sandbox.' if PAYPAL_MODE=='sandbox' else '' }paypal.com/v1/payments/payment"

    creds = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    encoded_creds = base64.b64encode(creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    token_res = requests.post(token_url, data=data, headers=headers)
    if token_res.status_code != 200:
        flash("Error getting PayPal token.")
        return redirect(url_for('cart_bp.view_cart'))
    access_token = token_res.json()['access_token']

    # 4) Create Payment
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    desc_text = f"Purchase from Online Bookstore (User ID: {user_id})"
    if method == 'delivery':
        desc_text += " + Delivery"

    paypal_payment = {
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "transactions": [{
            "amount": {
                "total": f"{total:.2f}",
                "currency": "USD"
            },
            "description": desc_text
        }],
        "redirect_urls": {
            "return_url": url_for('cart_bp.paypal_success', _external=True),
            "cancel_url": url_for('cart_bp.paypal_cancel', _external=True)
        }
    }

    payment_res = requests.post(payment_url, json=paypal_payment, headers=headers)
    if payment_res.status_code not in (200, 201):
        flash("Error creating PayPal payment.")
        return redirect(url_for('cart_bp.view_cart'))

    payment_data = payment_res.json()
    approval_url = None
    for link in payment_data["links"]:
        if link["rel"] == "approval_url":
            approval_url = link["href"]
            break

    if not approval_url:
        flash("Could not find PayPal approval link.")
        return redirect(url_for('cart_bp.view_cart'))

   
    session['paypal_payment_id'] = payment_data['id']
    session['checkout_total'] = total

    return redirect(approval_url)

@cart_bp.route('/paypal_success')
@user_required
def paypal_success():
    """
    After PayPal approval, we finalize the payment.
    If success => record purchase, purchase_items, clear cart,
    and if delivery => create a row in 'deliveries' with status='Pending'.
    """
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    session_pid = session.get('paypal_payment_id')
    if not payment_id or not payer_id or payment_id != session_pid:
        flash("Payment mismatch or missing payment info.")
        return redirect(url_for('cart_bp.view_cart'))

    token_url = f"https://api.{ 'sandbox.' if PAYPAL_MODE=='sandbox' else '' }paypal.com/v1/oauth2/token"
    creds = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    encoded_creds = base64.b64encode(creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    token_res = requests.post(token_url, data=data, headers=headers)
    if token_res.status_code != 200:
        flash("Error getting PayPal token for execution.")
        return redirect(url_for('cart_bp.view_cart'))
    access_token = token_res.json()['access_token']

    exec_url = f"https://api.{ 'sandbox.' if PAYPAL_MODE=='sandbox' else '' }paypal.com/v1/payments/payment/{payment_id}/execute"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    execute_data = {"payer_id": payer_id}

    exec_res = requests.post(exec_url, json=execute_data, headers=headers)
    if exec_res.status_code not in (200, 201):
        flash("Error executing PayPal payment.")
        return redirect(url_for('cart_bp.view_cart'))

    payment_info = exec_res.json()
    if payment_info.get('state') == 'approved':
        total_paid = session.get('checkout_total', 0.0)
        user_id = session['user_id']

        with create_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO purchases(user_id, payment_amount, payment_date, payment_status, paypal_transaction_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                total_paid,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Completed',
                payment_info['id']
            ))
            purchase_id = cursor.lastrowid

            cursor.execute("SELECT id FROM cart WHERE user_id=?", (user_id,))
            cart_row = cursor.fetchone()
            if cart_row:
                cart_id = cart_row[0]
                cursor.execute("""
                    SELECT book_id, quantity
                    FROM cart_items
                    WHERE cart_id=?
                """, (cart_id,))
                cart_items = cursor.fetchall()

                for item in cart_items:
                    book_id = item[0]
                    qty = item[1]
                   
                    cursor.execute("SELECT price FROM books WHERE id=?", (book_id,))
                    row = cursor.fetchone()
                    price_now = row[0] if row else 0

                   
                    cursor.execute("""
                        INSERT INTO purchase_items(purchase_id, book_id, quantity, price_at_purchase)
                        VALUES (?, ?, ?, ?)
                    """, (purchase_id, book_id, qty, price_now))

                    
                    cursor.execute("""
                        UPDATE books
                        SET quantity = quantity - ?
                        WHERE id = ?
                    """, (qty, book_id))

                
                cursor.execute("DELETE FROM cart_items WHERE cart_id=?", (cart_id,))

            method = session.get('delivery_method', 'pickup')
            if method == 'delivery':
                address = session.get('delivery_address', '')
                cursor.execute("""
                    INSERT INTO deliveries (purchase_id, driver_id, address, status)
                    VALUES (?, NULL, ?, 'Pending')
                """, (purchase_id, address))

            conn.commit()

        session.pop('paypal_payment_id', None)
        session.pop('checkout_total', None)
        session.pop('delivery_method', None)
        session.pop('delivery_address', None)

        flash("Payment successful! Your purchase has been recorded.")
        return redirect(url_for('user_bp.user_home2'))  # or whichever home
    else:
        flash("Payment not approved.")
        return redirect(url_for('cart_bp.view_cart'))

@cart_bp.route('/paypal_cancel')
@user_required
def paypal_cancel():
    flash("Payment cancelled.")
    return redirect(url_for('cart_bp.view_cart'))
