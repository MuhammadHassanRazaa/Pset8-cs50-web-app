import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from datetime import datetime
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, success

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    purchaces = db.execute(
        "SELECT Symbol, Name, Share as Shares, Unit_Price as 'Unit Price', (Share * Unit_Price) as Total from buy where user_id = :idd",idd =session["user_id"])

    total_price = 0
    for p in purchaces:
        total_price += p["Total"]
    cash_available = db.execute("Select cash from users where id= :userid",
                                    userid = session["user_id"])[0]["cash"]
    total_price += cash_available

    return render_template("index.html", purchaces=purchaces, cash=cash_available, total=total_price)

@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    username = request.args.get("username")

    if len(username) < 1:
        return jsonify(False)

    check_username = db.execute(
        "SELECT username FROM users WHERE username = :un", un=username)

    if len(check_username) == 0:
        return jsonify(True)
    else:
        return jsonify(False)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Missing Symbol", 400)

        elif not request.form.get("shares"):
            return apology("Missing share quantity", 400)

        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) < 1:
            return apology("Must be an integer and at least 1", 400)

        share = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        qouted_data = lookup(symbol)

        if not qouted_data:
            return apology("Symbol not valid", 400)

        price = float(qouted_data["price"])
        symbol = qouted_data["symbol"]
        cash_available = db.execute("Select cash from users where id= :userid",
                                            userid = session["user_id"])[0]["cash"]

        if (float(price) * int(share)) > float(cash_available):
            return apology("Less Cash", 400)
        else:
            cash_available = cash_available - (price * share)
            stocks = db.execute(
            "SELECT * FROM buy WHERE Symbol = :symbol AND user_id = :idd ", symbol=symbol, idd=session["user_id"])


            if len(stocks) == 0:

                db.execute("INSERT into buy (user_id, Symbol, Name, Share, Unit_Price, Total) VALUES (:userid, :symbol, :name, :share, :price, :total)",
                                    userid= session["user_id"], symbol = symbol, name = qouted_data["name"], share = share,
                                                price=price, total = (price * share) )
            else:
                share = share + int(stocks[0]['Share'])
                total = (price * share) + float(stocks[0]['Total'])
                db.execute("update  buy set Share = :share, Unit_Price = :price, Total = :total where Symbol = :symbol and user_id =:idd",
                                share=share, symbol=symbol, idd=session["user_id"], price=price, total=total)
            db.execute("UPDATE users set cash = :cash where id =:idd", cash=cash_available, idd=session["user_id"])
            db.execute("insert into History ('user_id', 'Symbol', 'Share', 'Price') VALUES(:idd, :symbol, :share, :price)",
                            idd = session["user_id"], symbol=symbol, share= int(request.form.get("shares")),
                                price=price)
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    history = db.execute("SELECT * from history where user_id = :idd", idd=session["user_id"])
    return render_template("history.html", history=history)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Must Provide a Symbol", 400)
        qouted_data = lookup(request.form.get("symbol"))
        if not qouted_data:
            return apology("Symbol not valid", 400)
        return render_template("quoted.html", company=qouted_data["name"],
                                symbol=qouted_data["symbol"], price=qouted_data["price"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        session.clear()

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password Again was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password again", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password doesn't match", 400)

        else:
            rows = db.execute(
               "SELECT * FROM users WHERE username = :user", user=request.form.get("username"))
            if len(rows) == 1:
                return apology("Username already taken")

            db.execute("INSERT INTO users ('username','hash') Values(:username, :password)",
                        username=request.form.get("username"),
                        password= generate_password_hash(request.form.get("password")))
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]

            # Redirect user to home page
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/passChange", methods=["GET", "POST"])
@login_required
def passChange():
    if request.method == "POST":
        if not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("passwordagain"):
            return apology("must provide password again", 400)

        elif request.form.get("password") != request.form.get("passwordagain"):
            return apology("Password doesn't match", 400)

        db.execute("UPDATE users set hash = :passw where id = :id",
                passw=generate_password_hash(request.form.get("password")), id=session["user_id"])

        return success("Password Change Successfuly", 200)
    else:
        return render_template("passChange.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        if not request.form.get("symbol") or request.form.get("symbol") == "":
            return apology("Symbol is required", 400)
        elif not request.form.get("shares"):
            return apology("Share is required", 400)
        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) < 1:
            return apology("Must be an integer and at least 1", 400)
        symbol = request.form.get("symbol")
        inputted_share = int(request.form.get("shares"))
        purchases = db.execute("select * from buy where user_id = :idd and Symbol= :symbol",
                                    idd=session["user_id"], symbol=symbol)

        if int(purchases[0]["Share"]) >= inputted_share:
            quoted_data = lookup(symbol)
            sell_price = float(quoted_data["price"]) * inputted_share
            cash_available = db.execute("SELECT cash from users where id = :uid", uid=session["user_id"])[0]['cash']
            cash_available += sell_price
            share_left = int(purchases[0]["Share"]) - inputted_share
            total_left = float(purchases[0]["Total"]) - sell_price
            if int(purchases[0]["Share"]) == inputted_share:
                db.execute("Delete from buy where Symbol = :symbol and user_id = :uid", symbol=symbol, uid=session["user_id"])
            elif int(purchases[0]["Share"]) > inputted_share:
                db.execute("update buy set Share = :share, Total = :total where Symbol = :symbol and user_id = :uid",
                        symbol = symbol, uid = session["user_id"], share=share_left, total=total_left )
            db.execute("update users set cash = :cash where id = :uid", uid=session["user_id"], cash=cash_available )
            db.execute("insert into History ('user_id', 'Symbol', 'Share', 'Price') VALUES(:idd, :symbol, :share, :price)",
                        idd = session["user_id"], symbol=symbol, share=(-1 * inputted_share),
                        price = float(quoted_data["price"]) )
            return redirect("/")
        else:
            return apology("Too Many Shares", 400)

    else:
        symbols = db.execute("select Symbol from buy where user_id = :idd", idd=session["user_id"])
        return render_template("sell.html", options=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
