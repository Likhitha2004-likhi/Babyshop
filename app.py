from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask import abort
from datetime import datetime
from flask import session, redirect, url_for, request, render_template


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"



app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # CHANGE this to a strong secret in real app


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            age_group TEXT,
            type TEXT,
            image TEXT
        )
    """)
    conn.commit()
    conn.close()
    return "Table created successfully!"


@app.route("/create-users-table")
def create_users_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    return "Users table created successfully!"


@app.route("/create-purchases-table")
def create_purchases_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    conn.close()
    return "Purchases table created successfully!"





@app.route("/")
def home():
    return render_template("home.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/dress")
def dress():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products WHERE type = ?", ("Dress",)).fetchall()
    conn.close()
    return render_template("dress.html", products=products)

@app.route('/nondress')
def non_dress():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products WHERE type = 'Non-Dress'").fetchall()
    conn.close()
    return render_template('nondress.html', products=products)

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template(
                "admin_login.html",
                error="Invalid admin credentials"
            )

    return render_template("admin_login.html")


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    total_products = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_orders = conn.execute(
        "SELECT COUNT(*) FROM purchases"
    ).fetchone()[0]

    total_revenue = conn.execute(
        """
        SELECT COALESCE(SUM(p.price * pu.quantity), 0)
        FROM purchases pu
        JOIN products p ON pu.product_id = p.id
        """
    ).fetchone()[0]

    products = conn.execute("SELECT * FROM products").fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_products=total_products,
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
        products=products
    )




@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        return "Product not found", 404

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        age_group = request.form["age_group"]
        type_ = request.form["type"]
        image = request.form["image"]

        conn.execute("""
            UPDATE products
            SET name = ?, price = ?, age_group = ?, type = ?, image = ?
            WHERE id = ?
        """, (name, price, age_group, type_, image, product_id))

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template("edit_product.html", product=product)





@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))



@app.route('/admin/delete-product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_dashboard'))




@app.route("/admin/add-product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        age_group = request.form["age_group"]
        type_ = request.form["type"]
        image = request.form["image"]

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO products (name, price, age_group, type, image) VALUES (?, ?, ?, ?, ?)",
            (name, price, age_group, type_, image)
        )
        conn.commit()
        conn.close()

        return redirect("/admin/dashboard")

    # If GET request, just render form
    return render_template("add_product.html")


@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    # Initialize cart if not present
    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    # Increment quantity if already in cart
    if str(product_id) in cart:
        cart[str(product_id)] += 1
    else:
        cart[str(product_id)] = 1

    session['cart'] = cart  # Save back to session

    return redirect(request.referrer or url_for('home'))



@app.route("/cart")
def cart():
    cart = session.get('cart', {})
    product_ids = list(cart.keys())

    products = []
    total_price = 0

    if product_ids:
        placeholders = ','.join('?' for _ in product_ids)
        query = f"SELECT * FROM products WHERE id IN ({placeholders})"
        conn = get_db_connection()
        rows = conn.execute(query, product_ids).fetchall()
        conn.close()

        for row in rows:
            qty = cart.get(str(row['id']), 0)
            total = row['price'] * qty
            total_price += total
            products.append({
                'id': row['id'],
                'name': row['name'],
                'price': row['price'],
                'age_group': row['age_group'],
                'image': row['image'],
                'quantity': qty,
                'total': total
            })

    return render_template("cart.html", products=products, total_price=total_price)


@app.route('/remove-from-cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})

    # Remove the product if it exists in the cart
    product_id_str = str(product_id)
    if product_id_str in cart:
        del cart[product_id_str]
        session['cart'] = cart  # Save changes back to session

    return redirect(url_for('cart'))



@app.route('/buy-now/<int:product_id>', methods=['GET', 'POST'])
def buy_now(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        return "Product not found", 404

    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO purchases (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            """,
            (session['user_id'], product_id, 1)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('thank_you', product_id=product_id))

    conn.close()
    return render_template("checkout.html", product=product)



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already registered. Please log in."
        conn.close()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("profile"))
        else:
            return "Invalid email or password."
    return render_template("login.html")



@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    purchases = conn.execute("""
        SELECT p.name, pu.quantity, pu.purchase_date
        FROM purchases pu
        JOIN products p ON pu.product_id = p.id
        WHERE pu.user_id = ?
    """, (user_id,)).fetchall()
    conn.close()

    return render_template("profile.html", user=user, purchases=purchases)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))



@app.route("/admin/users")
def list_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, name, email FROM users").fetchall()
    conn.close()
    return render_template("users.html", users=users)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()

    # Fetch current product
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        return "Product not found", 404

    price = product['price']
    lower_bound = price * 0.8
    upper_bound = price * 1.2

    # STEP 1: Price + type based recommendations
    recommendations = conn.execute(
        """
        SELECT * FROM products
        WHERE type = ?
          AND id != ?
          AND price BETWEEN ? AND ?
        LIMIT 10
        """,
        (product['type'], product_id, lower_bound, upper_bound)
    ).fetchall()

    # STEP 2: Fill remaining with random same-type products
    if len(recommendations) < 10:
        remaining = 10 - len(recommendations)

        extra_recommendations = conn.execute(
            """
            SELECT * FROM products
            WHERE type = ?
              AND id != ?
              AND id NOT IN ({})
            ORDER BY RANDOM()
            LIMIT ?
            """.format(",".join(str(r["id"]) for r in recommendations) or "0"),
            (product['type'], product_id, remaining)
        ).fetchall()

        recommendations = recommendations + extra_recommendations

    conn.close()

    return render_template(
        'product_detail.html',
        product=product,
        recommendations=recommendations
    )


@app.route('/thank-you/<int:product_id>')
def thank_you(product_id):
    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()
    conn.close()

    return render_template("thank_you.html", product=product)



@app.route('/admin/orders')
def admin_orders():
    conn = get_db_connection()

    orders = conn.execute("""
        SELECT 
            purchases.id,
            users.name AS user_name,
            products.name AS product_name,
            products.price,
            purchases.quantity,
            purchases.purchase_date
        FROM purchases
        JOIN users ON purchases.user_id = users.id
        JOIN products ON purchases.product_id = products.id
        ORDER BY purchases.purchase_date DESC
    """).fetchall()

    conn.close()

    return render_template('admin_orders.html', orders=orders)



if __name__ == "__main__":
    app.run(debug=True)
