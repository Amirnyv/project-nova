import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash
)

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from openai import OpenAI
from dotenv import load_dotenv

from agents.stock_agent import analyze_stock
from agents.portfolio_agent import (
    buy_stock,
    sell_stock,
    get_portfolio,
    get_trade_history
)

from agents.project_agent import (
    create_project,
    get_projects
)

from database import get_db, init_db
from user_model import User, get_user_by_id


# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing from the .env file."
    )


# -------------------------------------------------
# LOGIN MANAGER
# -------------------------------------------------

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message = (
    "Please log in to access Project Nova."
)


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)


# -------------------------------------------------
# DATABASE
# -------------------------------------------------

init_db()


# -------------------------------------------------
# OPENAI
# -------------------------------------------------

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# -------------------------------------------------
# SIGN UP
# -------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not username or not email or not password:
            flash(
                "Username, email, and password are required."
            )

            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.")

            return render_template("signup.html")

        if len(password) < 8:
            flash(
                "Password must be at least 8 characters."
            )

            return render_template("signup.html")

        password_hash = generate_password_hash(
            password
        )

        connection = get_db()

        try:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    password_hash
                )
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    email,
                    password_hash
                )
            )

            user_id = cursor.lastrowid

            connection.execute(
                """
                INSERT INTO portfolios (
                    user_id,
                    cash
                )
                VALUES (?, ?)
                """,
                (
                    user_id,
                    10000.00
                )
            )

            connection.commit()

        except sqlite3.IntegrityError:

            connection.rollback()

            flash(
                "That username or email is already registered."
            )

            connection.close()

            return render_template("signup.html")

        connection.close()

        user = User(
            user_id,
            username,
            email
        )

        login_user(user)

        return redirect(url_for("home"))

    return render_template("signup.html")


# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db()

        user_row = connection.execute(
            """
            SELECT
                id,
                username,
                email,
                password_hash
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        connection.close()

        if (
            user_row is None
            or not check_password_hash(
                user_row["password_hash"],
                password
            )
        ):
            flash(
                "Incorrect email or password."
            )

            return render_template("login.html")

        user = User(
            user_row["id"],
            user_row["username"],
            user_row["email"]
        )

        login_user(user)

        return redirect(url_for("home"))

    return render_template("login.html")


# -------------------------------------------------
# LOGOUT
# -------------------------------------------------

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("login"))


# -------------------------------------------------
# HOME
# -------------------------------------------------

@app.route("/")
@login_required
def home():

    return render_template(
        "index.html",
        user=current_user
    )


# -------------------------------------------------
# CHAT
# -------------------------------------------------

@app.route("/chat", methods=["POST"])
@login_required
def chat():

    data = request.get_json() or {}

    user_message = data.get(
        "message",
        ""
    ).strip()

    conversation_history = data.get(
        "history",
        []
    )

    if not user_message:
        return jsonify({
            "error": "A message is required."
        }), 400


    # -------------------------------------------------
    # OPENAI MESSAGE CONTEXT
    # -------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are Project Nova, an intelligent AI assistant. "
                "Remember the current conversation and remain "
                "consistent with its topic and context. "
                "If the conversation is about Python, continue "
                "helping with Python unless the user changes subjects. "
                "If it is about stocks, continue discussing stocks. "
                "Give clear, helpful, and professional responses."
            )
        }
    ]


    for item in conversation_history:

        role = item.get("role")

        content = item.get(
            "content",
            ""
        ).strip()

        if (
            role in ("user", "assistant")
            and content
        ):

            messages.append({
                "role": role,
                "content": content
            })


    messages.append({
        "role": "system",
        "content": (
            f"The current conversation contains "
            f"{len(conversation_history)} previous messages. "
            f"Use the earlier discussion when answering "
            f"if it is relevant."
        )
    })


    messages.append({
        "role": "user",
        "content": user_message
    })


    lower_message = user_message.lower()


    # -------------------------------------------------
    # TRADE HISTORY
    # -------------------------------------------------

    if "trade history" in lower_message:

        trades = get_trade_history(
    int(current_user.id)
)

        if not trades:

            return jsonify({
                "reply": (
                    "📜 Trade History\n\n"
                    "No paper trades recorded yet."
                )
            })

        history_text = ""

        for trade in reversed(trades):

            history_text += (
                f"\n\n{trade['action']} "
                f"{trade['symbol']}\n"
                f"Shares: {trade['shares']}\n"
                f"Price: ${trade['price']:.2f}\n"
                f"Total: ${trade['total']:.2f}\n"
                f"Time: {trade['timestamp']}"
            )

        return jsonify({
            "reply": (
                f"📜 Paper Trade History"
                f"{history_text}\n\n"
                f"🧪 Simulation Mode"
            )
        })


    # -------------------------------------------------
    # SHOW PORTFOLIO
    # -------------------------------------------------

    if "portfolio" in lower_message:

        portfolio = get_portfolio(
    int(current_user.id)
)

        positions = portfolio["positions"]

        total_positions_value = 0

        position_text = ""


        for symbol, position in positions.items():

            stock = analyze_stock(symbol)

            if "error" in stock:

                current_price = position[
                    "average_price"
                ]

            else:

                current_price = stock["price"]


            shares = position["shares"]

            average_price = position[
                "average_price"
            ]


            market_value = (
                shares * current_price
            )

            cost_basis = (
                shares * average_price
            )

            profit_loss = (
                market_value - cost_basis
            )

            total_positions_value += (
                market_value
            )


            position_text += (
                f"\n\n📈 {symbol}\n"
                f"Shares: {shares}\n"
                f"Average Price: "
                f"${average_price:.2f}\n"
                f"Current Price: "
                f"${current_price:.2f}\n"
                f"Market Value: "
                f"${market_value:.2f}\n"
                f"P/L: ${profit_loss:+.2f}"
            )


        if not positions:

            position_text = (
                "\n\nNo positions yet."
            )


        portfolio_value = (
            portfolio["cash"]
            + total_positions_value
        )


        total_profit_loss = (
            portfolio_value
            - 10000.00
        )


        return jsonify({
            "reply": (
                f"💼 Paper Portfolio\n\n"
                f"💵 Cash: "
                f"${portfolio['cash']:.2f}\n"
                f"📊 Investments: "
                f"${total_positions_value:.2f}\n"
                f"💰 Portfolio Value: "
                f"${portfolio_value:.2f}\n"
                f"📈 Total P/L: "
                f"${total_profit_loss:+.2f}"
                f"{position_text}\n\n"
                f"🧪 Simulation Mode"
            )
        })


    # -------------------------------------------------
    # BUY
    # Example:
    # buy AAPL 2
    # -------------------------------------------------

    if lower_message.startswith("buy "):

        parts = user_message.split()

        if len(parts) != 3:

            return jsonify({
                "reply": (
                    "Use this format:\n"
                    "buy AAPL 2"
                )
            })

        symbol = parts[1].upper()

        try:

            shares = float(
                parts[2]
            )

        except ValueError:

            return jsonify({
                "reply": (
                    "Enter shares as a number."
                )
            })


        stock = analyze_stock(symbol)

        if "error" in stock:

            return jsonify({
                "reply": (
                    f"Stock Agent Error: "
                    f"{stock['error']}"
                )
            })


        result = buy_stock(
    int(current_user.id),
    symbol,
    shares,
    stock["price"]
)


        if "error" in result:

            return jsonify({
                "reply": result["error"]
            })


        return jsonify({
            "reply": (
                f"✅ Paper Trade Executed\n\n"
                f"Bought {result['shares']} "
                f"shares of {result['symbol']}\n"
                f"Price: ${result['price']}\n"
                f"Cost: ${result['cost']}\n\n"
                f"Cash Remaining: "
                f"${result['cash']}\n"
                f"🧪 Simulation Mode"
            )
        })


    # -------------------------------------------------
    # SELL
    # Example:
    # sell AAPL 1
    # -------------------------------------------------

    if lower_message.startswith("sell "):

        parts = user_message.split()

        if len(parts) != 3:

            return jsonify({
                "reply": (
                    "Use this format:\n"
                    "sell AAPL 1"
                )
            })


        symbol = parts[1].upper()


        try:

            shares = float(
                parts[2]
            )

        except ValueError:

            return jsonify({
                "reply": (
                    "Enter shares as a number."
                )
            })


        stock = analyze_stock(symbol)


        if "error" in stock:

            return jsonify({
                "reply": (
                    f"Stock Agent Error: "
                    f"{stock['error']}"
                )
            })


        result = sell_stock(
    int(current_user.id),
    symbol,
    shares,
    stock["price"]
)


        if "error" in result:

            return jsonify({
                "reply": result["error"]
            })


        return jsonify({
            "reply": (
                f"✅ Paper Trade Executed\n\n"
                f"Sold {result['shares']} "
                f"shares of {result['symbol']}\n"
                f"Price: ${result['price']}\n"
                f"Proceeds: "
                f"${result['proceeds']}\n\n"
                f"Cash Available: "
                f"${result['cash']}\n"
                f"🧪 Simulation Mode"
            )
        })


    # -------------------------------------------------
    # STOCK ANALYSIS
    # -------------------------------------------------

    stock_keywords = [
        "aapl",
        "tsla",
        "btc",
        "bitcoin",
        "stock",
        "stocks",
        "analyze"
    ]


    if any(
        word in lower_message
        for word in stock_keywords
    ):

        symbol = None


        if "aapl" in lower_message:

            symbol = "AAPL"


        elif "tsla" in lower_message:

            symbol = "TSLA"


        elif (
            "btc" in lower_message
            or "bitcoin" in lower_message
        ):

            symbol = "BTC"


        if symbol:

            result = analyze_stock(
                symbol
            )


            if "error" in result:

                return jsonify({
                    "reply": (
                        f"Stock Agent Error: "
                        f"{result['error']}"
                    )
                })


            return jsonify({

                "reply": (

                    f"📈 {result['company']} "
                    f"({result['symbol']})\n\n"

                    f"💲 Current Price: "
                    f"${result['price']}\n"

                    f"📊 Daily Change: "
                    f"{result['change']}%\n\n"

                    f"📉 20-Day Average: "
                    f"${result['ma20']}\n"

                    f"📉 50-Day Average: "
                    f"${result['ma50']}\n"

                    f"⚡ RSI (14): "
                    f"{result['rsi']}\n"

                    f"🚀 5-Day Momentum: "
                    f"{result['momentum']}%\n"

                    f"⚠️ Volatility: "
                    f"{result['volatility']}%\n\n"

                    f"🧠 Nova Score: "
                    f"{result['score']}/100\n"

                    f"🎯 Signal: "
                    f"{result['signal']}\n"

                    f"⚠️ Risk: "
                    f"{result['risk']}\n\n"

                    f"💡 Analysis:\n"
                    f"{result['reason']}\n\n"

                    f"🌐 {result['mode']}"
                ),

                "stock_data": {

                    "symbol":
                        result["symbol"],

                    "dates":
                        result["chart_dates"],

                    "prices":
                        result["chart_prices"],

                    "ma20":
                        result["chart_ma20"],

                    "ma50":
                        result["chart_ma50"]
                }
            })


    # -------------------------------------------------
    # NORMAL OPENAI CHAT
    # -------------------------------------------------

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )


    reply = (
        response
        .choices[0]
        .message
        .content
    )


    return jsonify({
        "reply": reply
    })


# -------------------------------------------------
# RUN
# -------------------------------------------------

@app.route("/api/projects", methods=["GET"])
@login_required
def list_projects():
    projects = get_projects(
        int(current_user.id)
    )

    print(projects)

    return jsonify({
        "projects": projects
    })


@app.route("/api/projects", methods=["POST"])
@login_required
def add_project():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    result = create_project(
        int(current_user.id),
        name,
        description
    )

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 201

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5001
    )