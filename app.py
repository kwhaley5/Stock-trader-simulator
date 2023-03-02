import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks""" #I need to figure out how to group thins

    stock_value = 0

    summarys = db.execute("SELECT stock, (SUM(buy) - SUM(sell)) AS shares, symbol FROM transactions WHERE name = ? GROUP BY stock", session["user_id"])
    for i in range(len(summarys)):
        current_quote = lookup(summarys[i]['symbol'])
        value = summarys[i]['shares'] * list(current_quote.values())[1]
        summarys[i]['currentPrice'] = usd(list(current_quote.values())[1])

        stock_value += value
        summarys[i]['holdings'] = usd(stock_value)


    totals = {}

    total_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    grand_total = total_cash[0]['cash'] + stock_value

    totals['totalCash'] = usd(total_cash[0]['cash'])
    totals['grandTotal'] = usd(grand_total)

    return render_template("index.html", summarys=summarys, totals=totals)

@app.route("/balance", methods=["GET", "POST"])
@login_required
def balance():

    if request.method == "POST":
        amount = request.form.get("amount")
        if not amount:
            return apology("Enter amount")
        if float(amount) < 0:
            return apology("Must be positive")

        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        new_balance = balance[0]['cash'] + float(amount)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])

        new_balance = usd(new_balance)

        return redirect("/balance")

    else:
        uBalance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        uBalance[0]['cash'] = usd(uBalance[0]['cash'])

        return render_template("balance.html", balances=uBalance)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        item = request.form.get("symbol")
        buy_quote = lookup(item)
        if not buy_quote:
            return apology("Stock not Found")

        shares = request.form.get("shares")
        if not shares or int(shares) < 0:
            return apology("Please enter valid amount")

        total = float(shares) * list(buy_quote.values())[1]

        db.execute("INSERT into transactions (name, stock, price, buy, total, symbol, sell) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"], list(buy_quote.values())[0], list(buy_quote.values())[1], shares, total, item, 0)

        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        new_balance = balance[0]['cash'] - total

        if new_balance < 0:
            return apology("not enough cash")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    buys = db.execute("SELECT stock, price, buy, symbol, total FROM transactions WHERE buy > 0 AND name = ?", session["user_id"])

    for i in range(len(buys)):
        buys[i]['price'] = usd(buys[i]['price'])
        buys[i]['total'] = usd(buys[i]['total'])

    sells = db.execute("SELECT stock, price, sell, symbol, total FROM transactions WHERE sell > 0 AND name = ?", session["user_id"])

    for j in range(len(sells)):
        sells[j]['price'] = usd(sells[j]['price'])
        sells[j]['total'] = usd(sells[j]['total'])

    return render_template("history.html", buys=buys, sells=sells)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if not quote:
            return apology("Stock not Found")

        db.execute("INSERT into stocks (name, price, symbol, user) VALUES(?, ?, ?, ?)", list(quote.values())[0], list(quote.values())[1], list(quote.values())[2], session["user_id"])

        return redirect("/quote")

    else:

        history = db.execute("SELECT * FROM stocks WHERE user = ?", session["user_id"])

        return render_template("quote.html", stocks=history)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            return apology("Provide Username")

        password = request.form.get("password")
        if not password:
            return apology("Provide Password")

        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("Confirm Password")

        if password != confirmation:
            return apology ("Passwords do not match")

        hash = generate_password_hash(password)

        db.execute("INSERT into users (username, hash) VALUES(?, ?)", username, hash)

        return redirect("/register")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    symbols = db.execute("SELECT symbol FROM transactions WHERE name = ? GROUP BY stock", session["user_id"])
    if not symbols:
        return apology("You don't own that stock")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        shares = request.form.get("shares")
        if not shares:
            return apology("Please enter valid number")

        total = float(shares) * list(quote.values())[1]

        db.execute("INSERT into transactions (name, stock, price, buy, total, symbol, sell) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"], list(quote.values())[0], list(quote.values())[1], 0, total, symbol, shares)

        remainder = db.execute("SELECT (SUM(buy) - SUM(sell)) AS shares FROM transactions WHERE name = ? GROUP BY stock", session["user_id"])
        if remainder[0]['shares'] < 0:
            return apology("Not enough shares to sell")

        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        new_balance = balance[0]['cash'] + total

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])


        return redirect("/")

    return render_template("sell.html", symbols=symbols)
