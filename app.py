import sqlite3
from flask import Flask

app = Flask(__name__)

app.secret_key = '99869b14fc462c20535e529a0c16781a'

DATABASE = 'bookstore.db'

def create_tables():
    """Creates database tables if they do not already exist."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

   
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

   
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                employment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

      
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price REAL NOT NULL,
                cover_image BLOB,
                pdf_file BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

      
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cart_id) REFERENCES cart(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );
        ''')

      
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                payment_amount REAL NOT NULL,
                payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                payment_status TEXT NOT NULL,
                paypal_transaction_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

      
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                price_at_purchase REAL,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );
        ''')

        conn.commit()
    print("Database tables created or verified!")

def update_db_schema():
    """Updates the existing DB with new columns/tables."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

        try:
            cursor.execute("ALTER TABLE books ADD COLUMN condition TEXT;")
            print("Added 'condition' column to 'books' table.")
        except sqlite3.OperationalError:
            print("'condition' column already exists in 'books' table.")

        try:
            cursor.execute("ALTER TABLE books ADD COLUMN quantity INTEGER DEFAULT 0;")
            print("Added 'quantity' column to 'books' table.")
        except sqlite3.OperationalError:
            print("'quantity' column already exists in 'books' table.")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                joined_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

 
        try:
        
            cursor.execute("DROP TABLE IF EXISTS deliveries;")
           
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_id INTEGER NOT NULL,
                    driver_id INTEGER,                 -- allow NULL here
                    address TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    delivered_date DATETIME,
                    FOREIGN KEY (purchase_id) REFERENCES purchases(id),
                    FOREIGN KEY (driver_id) REFERENCES drivers(id)
                );
            ''')
            print("Deliveries table re-created with driver_id as nullable.")
        except sqlite3.OperationalError as e:
            print(f"Error re-creating deliveries table: {e}")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile_pics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pic BLOB,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                rating INTEGER,
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );
        ''')

       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );
        ''')

        conn.commit()
    print("Database schema updated with new columns and tables!")

from flask import Flask

app = Flask(__name__)
app.secret_key = '99869b14fc462c20535e529a0c16781a'

@app.route('/')
def home():
    return "Hello from Online Bookstore!"

if __name__ == '__main__':
   
    create_tables()

    update_db_schema()

    from register import accounts_bp
    app.register_blueprint(register_bp)

    from login import login_bp
    app.register_blueprint(login_bp)

    from staffregistration import staffreg_bp
    app.register_blueprint(staffreg_bp)

    from bookmanagement import book_bp
    app.register_blueprint(book_bp)

    from analysis import analysis_bp
    app.register_blueprint(analysis_bp)

    from userhome import user_bp
    app.register_blueprint(user_bp)

    from cart import cart_bp
    app.register_blueprint(cart_bp)

    from mybooks import mybooks_bp
    app.register_blueprint(mybooks_bp)
    from delivery import delivery_bp
    app.register_blueprint(delivery_bp)



    app.run(debug=True)
