from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Book, Cart, Purchases 

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookstore.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  

db.init_app(app)
migrate = Migrate(app, db)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

      
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('register'))

      
        if User.query.filter_by(email=email).first():
            flash('Email is already in use. Please use another email.', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username is already taken. Choose another one.', 'danger')
            return redirect(url_for('register'))

      
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, username=username, password=hashed_password)

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')




ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

 
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user_id'] = "admin" 
            flash('Admin login successful!', 'success')
            return redirect(url_for('dashboard'))  
        
    
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('books')) 
        
        flash('Invalid username or password', 'danger')

    return render_template('login.html')








@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    books = Book.query.all()
    users = User.query.all()
    
    return render_template('dashboard.html', books=books, users=users)

@app.route('/add_book', methods=['POST'])
def add_book():
    if 'user_id' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    title = request.form['title']
    author = request.form['author']
    description = request.form['description']
    price = float(request.form['price'])
    
    new_book = Book(title=title, author=author, description=description, price=price)
    db.session.add(new_book)
    db.session.commit()
    
    flash('Book added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'user_id' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form['author']
        book.description = request.form['description']
        db.session.commit()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_book.html', book=book)

@app.route('/delete_book/<int:book_id>')
def delete_book(book_id):
    if 'user_id' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('dashboard'))



@app.route('/books')
def books():
    all_books = Book.query.all()
    return render_template('books.html', books=all_books)


@app.route('/add_to_cart/<int:book_id>', methods=['POST'])
def add_to_cart(book_id):
    if 'user_id' not in session:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    existing_item = Cart.query.filter_by(user_id=user_id, book_id=book_id).first()

    if existing_item:
        existing_item.quantity += 1  
    else:
        new_cart_item = Cart(user_id=user_id, book_id=book_id)
        db.session.add(new_cart_item)

    db.session.commit()
    flash('Book added to cart!', 'success')
    return redirect(url_for('books'))


@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    cart_items = Cart.query.filter_by(user_id=user_id).all()

    
    total_price = sum(item.book.price for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)



@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    if 'user_id' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    cart_item = Cart.query.get_or_404(cart_id)
    db.session.delete(cart_item)
    db.session.commit()

    flash('Book removed from cart!', 'success')
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    cart_items = Cart.query.filter_by(user_id=user_id).all()

    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('cart'))

  
    for item in cart_items:
        new_purchase = Purchases(user_id=user_id, book_id=item.book_id)
        db.session.add(new_purchase)
        db.session.delete(item)  

    db.session.commit()
    flash('Checkout successful! Your books are now available for access.', 'success')
    return redirect(url_for('purchased_books'))

@app.route('/purchased_books')
def purchased_books():
    if 'user_id' not in session:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    purchased_books = Purchases.query.filter_by(user_id=user_id).all()

    return render_template('purchased_books.html', purchased_books=purchased_books)


if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(debug=True)