import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = "fc49073ea49d45d78c613797800669b0"

DATABASE = "finance_tracker.db"


def calculate_installment_date(start_date_str, installment_number):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    return (start_date + timedelta(days=30 * installment_number)).strftime("%Y-%m-%d")


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            payment_method TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )
    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    if "username" in session:
        user_id = session["user_id"]
        username = session["username"]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()

        total_amount = sum(transaction[2] for transaction in transactions)
        total_upi = sum(
            transaction[2] for transaction in transactions if transaction[6] == "Credit"
        )
        total_cash = sum(
            transaction[2]
            for transaction in transactions
            if transaction[6] in ["Débito", "Pix", "Dinheiro"]
        )

        conn.close()

        return render_template(
            "index.html",
            username=username,
            total_amount=total_amount,
            total_upi=total_upi,
            total_cash=total_cash,
        )
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(
            "SELECT id, username FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        user = c.fetchone()
        conn.close()
        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password. Please try again.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = c.fetchone()
        if existing_user:
            flash("Username already exists. Please choose a different one.", "error")
        else:
            c.execute(
                "INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
                (username, email, phone, password),
            )
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/transactions")
def transactions():
    if "username" in session:
        user_id = session["user_id"]
        username = session["username"]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        conn.close()

        return render_template(
            "transaction.html", transactions=transactions, username=username
        )
    else:
        return redirect(url_for("login"))


@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    if "username" in session:
        user_id = session["user_id"]  # Assuming you store user_id in session
        date = request.form["date"] or datetime.today().strftime("%Y-%m-%d")
        category = request.form["category"]
        amount = float(request.form["amount"])
        payment_method = request.form["payment_method"]
        description = request.form["notes"]

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        if payment_method == "Credit":

            installments = int(request.form.get("installments", 1))
            installment_amount = amount / installments

            for i in range(installments):
                print(date)
                installment_date = calculate_installment_date(
                    date, i
                )  # Function to calculate due date for each installment
                c.execute(
                    "INSERT INTO transactions (user_id, date, category, amount, payment_method, description) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        installment_date,
                        category,
                        installment_amount,
                        payment_method,
                        description,
                    ),
                )
        else:
            c.execute(
                "INSERT INTO transactions (user_id, date, category, amount, payment_method, description) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, date, category, amount, payment_method, description),
            )

        conn.commit()
        conn.close()

        return redirect(url_for("transactions"))
    else:
        return redirect(url_for("login"))


@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):
    if "username" in session:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
        conn.close()
        flash("Transaction deleted successfully.", "success")
    else:
        flash("You must be logged in to delete a transaction.", "error")
    return redirect(url_for("transactions"))


@app.route("/daily_spending_data")
def daily_spending_data():
    if "username" in session:
        user_id = session["user_id"]

        # Fetch daily spending data from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(
            "SELECT date, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY date",
            (user_id,),
        )
        data = c.fetchall()
        conn.close()

        # Format data for Chart.js
        labels = [row[0] for row in data]
        amounts = [row[1] for row in data]

        return jsonify({"labels": labels, "amounts": amounts})
    else:
        return redirect(url_for("login"))


@app.route("/monthly_spending_data")
def monthly_spending_data():
    if "username" in session:
        user_id = session["user_id"]

        # Fetch monthly spending data from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(
            "SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY month",
            (user_id,),
        )
        data = c.fetchall()
        conn.close()

        # Format data for Chart.js
        labels = [datetime.strptime(row[0], "%Y-%m").strftime("%b %Y") for row in data]
        amounts = [row[1] for row in data]

        return jsonify({"labels": labels, "amounts": amounts})
    else:
        return redirect(url_for("login"))


from flask import session


@app.route("/statistics")
def statistics():
    # Retrieve the user's identifier from the session
    user_id = session.get("user_id")  # Assuming you store user ID in the session

    if user_id:
        # Fetch data for statistics page for the logged-in user from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Fetch total expenses for the logged-in user
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (user_id,))
        total_expenses_result = c.fetchone()
        total_expenses = total_expenses_result[0] or 0

        # Fetch expense breakdown by category for the logged-in user
        c.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category",
            (user_id,),
        )
        expense_by_category_result = c.fetchall()
        expense_by_category = (
            dict(expense_by_category_result) if expense_by_category_result else {}
        )

        # Fetch top spending categories for the logged-in user
        c.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5",
            (user_id,),
        )
        top_spending_categories_result = c.fetchall()
        top_spending_categories = (
            dict(top_spending_categories_result)
            if top_spending_categories_result
            else {}
        )

        conn.close()

        # Render the statistics page template with the fetched data
        return render_template(
            "statistics.html",
            total_expenses=total_expenses,
            expense_by_category=expense_by_category,
            top_spending_categories=top_spending_categories,
        )
    else:
        # Redirect to login page if user is not logged in
        return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
