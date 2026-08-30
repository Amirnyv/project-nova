import os
import sqlite3
import uuid
import stripe
import resend
from html import escape
import hashlib
import hmac

from itsdangerous import (
    URLSafeTimedSerializer,
    SignatureExpired,
    BadSignature
)
from datetime import datetime, timezone
import json

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    send_from_directory,
    Response,
    stream_with_context
)

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
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

stripe.api_key = os.getenv(
    "STRIPE_SECRET_KEY"
)

STRIPE_PRO_PRICE_ID = (
    os.getenv("STRIPE_PRO_PRICE_ID")
    or os.getenv("STRIPE_PRICE_ID")
)

STRIPE_MAX_PRICE_ID = os.getenv(
    "STRIPE_MAX_PRICE_ID"
)

# -------------------------------------------------
# EMAIL
# -------------------------------------------------

resend.api_key = os.getenv(
    "RESEND_API_KEY"
)

RESEND_FROM_EMAIL = (
    "Nova <hello@mail.workfieldhq.com>"
)
password_reset_serializer = (
    URLSafeTimedSerializer(
        app.secret_key
    )
)

PASSWORD_RESET_SALT = (
    "nova-password-reset"
)

PASSWORD_RESET_MAX_AGE = 3600


def send_welcome_email(
    email,
    username
):
    if not resend.api_key:
        print(
            "Welcome email skipped: "
            "RESEND_API_KEY is missing."
        )
        return

    safe_username = escape(
        username
    )

    try:
        resend.Emails.send({
            "from":
                RESEND_FROM_EMAIL,

            "to": [
                email
            ],

            "subject":
                "Welcome to Nova",

            "html": f"""
                <div style="
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: auto;
                    padding: 30px;
                ">
                    <h2>
                        Welcome to Nova, {safe_username}!
                    </h2>

                    <p>
                        Your Nova account is ready.
                    </p>

                    <p>
                        You can now use Nova to chat,
                        research, work on projects,
                        and more.
                    </p>

                    <p>
                        <a href="https://workfieldhq.com"
                           style="
                               display: inline-block;
                               padding: 12px 20px;
                               background: #111827;
                               color: white;
                               text-decoration: none;
                               border-radius: 8px;
                           ">
                            Open Nova
                        </a>
                    </p>

                    <p>
                        Thanks for joining Nova.
                    </p>
                </div>
            """
        })

    except Exception as error:
        print(
            "Welcome email error:",
            repr(error)
        )

def get_password_fingerprint(
    password_hash
):
    return hashlib.sha256(
        password_hash.encode("utf-8")
    ).hexdigest()


def generate_password_reset_token(
    user_id,
    password_hash
):
    return password_reset_serializer.dumps(
        {
            "user_id": user_id,
            "password_fingerprint":
                get_password_fingerprint(
                    password_hash
                )
        },
        salt=PASSWORD_RESET_SALT
    )


def verify_password_reset_token(
    token
):
    try:
        data = (
            password_reset_serializer.loads(
                token,
                salt=PASSWORD_RESET_SALT,
                max_age=PASSWORD_RESET_MAX_AGE
            )
        )

    except SignatureExpired:
        return None, "expired"

    except BadSignature:
        return None, "invalid"


    user_id = data.get(
        "user_id"
    )

    expected_fingerprint = data.get(
        "password_fingerprint"
    )


    if (
        not user_id
        or not expected_fingerprint
    ):
        return None, "invalid"


    connection = get_db()

    user_row = connection.execute(
        """
        SELECT
            id,
            email,
            password_hash
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    connection.close()


    if not user_row:
        return None, "invalid"


    current_fingerprint = (
        get_password_fingerprint(
            user_row["password_hash"]
        )
    )


    if not hmac.compare_digest(
        expected_fingerprint,
        current_fingerprint
    ):
        return None, "invalid"


    return user_row, None


def send_password_reset_email(
    email,
    reset_url
):
    if not resend.api_key:
        print(
            "Password reset email skipped: "
            "RESEND_API_KEY is missing."
        )
        return False


    try:
        resend.Emails.send({
            "from":
                RESEND_FROM_EMAIL,

            "to": [
                email
            ],

            "subject":
                "Reset your Nova password",

            "html": f"""
                <div style="
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: auto;
                    padding: 30px;
                ">
                    <h2>
                        Reset your Nova password
                    </h2>

                    <p>
                        We received a request to reset
                        your Nova password.
                    </p>

                    <p>
                        <a href="{escape(reset_url)}"
                           style="
                               display: inline-block;
                               padding: 12px 20px;
                               background: #111827;
                               color: white;
                               text-decoration: none;
                               border-radius: 8px;
                           ">
                            Reset Password
                        </a>
                    </p>

                    <p>
                        This link expires in 1 hour.
                    </p>

                    <p>
                        If you did not request this,
                        you can safely ignore this email.
                    </p>
                </div>
            """
        })

        return True

    except Exception as error:
        print(
            "Password reset email error:",
            repr(error)
        )

        return False

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

        password_hash = generate_password_hash(password)

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
            connection.close()

            flash(
                "That username or email is already registered."
            )
            return render_template("signup.html")

            connection.close()

        send_welcome_email(
            email,
            username
        )

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
            flash("Incorrect email or password.")
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
# FORGOT PASSWORD
# -------------------------------------------------

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if current_user.is_authenticated:
        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if email:

            connection = get_db()

            user_row = connection.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

            connection.close()

            if user_row:

                token = (
                    generate_password_reset_token(
                        user_row["id"],
                        user_row["password_hash"]
                    )
                )

                reset_url = url_for(
                    "reset_password",
                    token=token,
                    _external=True
                )

                send_password_reset_email(
                    user_row["email"],
                    reset_url
                )

        flash(
            "If an account exists with that email, "
            "a password reset link has been sent."
        )

        return redirect(
            url_for("forgot_password")
        )

    return render_template(
        "forgot_password.html"
    )

# -------------------------------------------------
# RESET PASSWORD
# -------------------------------------------------

@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    user_row, token_error = (
        verify_password_reset_token(
            token
        )
    )

    if token_error == "expired":

        flash(
            "That password reset link has expired. "
            "Please request a new one."
        )

        return redirect(
            url_for("forgot_password")
        )

    if token_error or not user_row:

        flash(
            "That password reset link is invalid. "
            "Please request a new one."
        )

        return redirect(
            url_for("forgot_password")
        )


    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        if len(password) < 8:

            flash(
                "Password must be at least 8 characters."
            )

            return render_template(
                "reset_password.html"
            )


        if password != confirm_password:

            flash(
                "Passwords do not match."
            )

            return render_template(
                "reset_password.html"
            )


        new_password_hash = (
            generate_password_hash(
                password
            )
        )


        connection = get_db()

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (
                new_password_hash,
                user_row["id"]
            )
        )

        connection.commit()
        connection.close()


        flash(
            "Your password has been reset. "
            "You can now log in."
        )

        return redirect(
            url_for("login")
        )


    return render_template(
        "reset_password.html"
    )

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
def landing():
    return render_template(
        "landing.html"
    )

@app.route("/privacy")
def privacy():
    return render_template(
        "privacy.html"
    )

@app.route("/refund-policy")
def refund_policy():
    return render_template(
        "refund.html"
    )

@app.route("/terms")
def terms():
    return render_template(
        "terms.html"
    )

@app.route("/contact")
def contact():
    return render_template(
        "contact.html"
    )

@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():

    data = request.get_json(
        silent=True
    ) or {}

    selected_plan = (
        data.get("plan")
        or "pro"
    ).strip().lower()


    price_ids = {
        "pro": STRIPE_PRO_PRICE_ID,
        "max": STRIPE_MAX_PRICE_ID
    }


    if selected_plan not in price_ids:

        return jsonify({
            "error": "Invalid subscription plan."
        }), 400


    selected_price_id = (
        price_ids[selected_plan]
    )


    if not selected_price_id:

        return jsonify({
            "error": (
                f"Stripe price for "
                f"{selected_plan.title()} "
                "is not configured."
            )
        }), 500


    try:

        metadata = {
            "user_id": str(
                current_user.id
            ),
            "plan": selected_plan
        }


        session = stripe.checkout.Session.create(
            mode="subscription",

            line_items=[
                {
                    "price":
                        selected_price_id,
                    "quantity": 1
                }
            ],

            customer_email=
                current_user.email,

            success_url=(
                request.host_url.rstrip("/")
                + "/app?checkout=success"
            ),

            cancel_url=(
                request.host_url.rstrip("/")
                + "/app?checkout=canceled"
            ),

            metadata=metadata,

            subscription_data={
                "metadata": metadata
            }
        )


        return jsonify({
            "url": session.url
        })


    except Exception as error:

        print(
            "Stripe checkout error:",
            repr(error)
        )

        return jsonify({
            "error":
                "Could not start checkout."
        }), 500

@app.route("/create-portal-session", methods=["POST"])
@login_required
def create_portal_session():

    subscription = get_active_subscription(
        int(current_user.id)
    )

    if not subscription:
        return jsonify({
            "error": "No active subscription found."
        }), 400


    connection = get_db()

    row = connection.execute(
        """
        SELECT provider_customer_id
        FROM subscriptions
        WHERE user_id = ?
        """,
        (
            int(current_user.id),
        )
    ).fetchone()

    connection.close()


    if (
        not row
        or not row["provider_customer_id"]
    ):
        return jsonify({
            "error": "Stripe customer is not available."
        }), 400


    try:

        portal_session = stripe.billing_portal.Session.create(
            customer=row["provider_customer_id"],
            return_url=(
                request.host_url.rstrip("/")
                + "/app"
            )
        )

        return jsonify({
            "url": portal_session.url
        })

    except Exception as error:

        print(
            "Stripe portal error:",
            repr(error)
        )

        return jsonify({
            "error": "Could not open subscription management."
        }), 500

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():

    payload = request.data

    signature = request.headers.get(
        "Stripe-Signature"
    )

    webhook_secret = os.getenv(
        "STRIPE_WEBHOOK_SECRET"
    )

    try:

        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret
        )

    except Exception as error:

        print(
            "Stripe webhook error:",
            repr(error)
        )

        return "", 400


    event_type = event["type"]

    data_object = (
    event["data"]["object"].to_dict()
)


    if event_type == "checkout.session.completed":

        user_id = (
            data_object
            .get("metadata", {})
            .get("user_id")
        )

        stripe_subscription_id = (
            data_object.get("subscription")
        )

        if user_id and stripe_subscription_id:

            user_id = int(user_id)

            try:

                stripe_subscription = (
                    stripe.Subscription.retrieve(
                        stripe_subscription_id
                    )
                )

                subscription_data = (
                    stripe_subscription.to_dict()
                )

                period_start_timestamp, period_end_timestamp = (
    get_stripe_period(
        subscription_data
    )
)

                purchased_plan = (
                    data_object
                    .get("metadata", {})
                    .get("plan", "pro")
                )

                if purchased_plan not in (
                    "pro",
                    "max"
                ):
                    purchased_plan = "pro"

                save_subscription(
                    user_id=user_id,
                    plan=purchased_plan,
                    status=subscription_data.get(
                        "status",
                        "active"
                    ),
                    provider="stripe",
                    provider_customer_id=(
                        data_object.get("customer")
                        or ""
                    ),
                    provider_subscription_id=(
                        stripe_subscription_id
                    ),
                    current_period_start=(
    stripe_timestamp_to_datetime(
        period_start_timestamp
    )
),
current_period_end=(
    stripe_timestamp_to_datetime(
        period_end_timestamp
    )
)
                )

            except Exception as error:

                print(
                    "Stripe subscription sync error:",
                    repr(error)
                )

                return "", 500


    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated"
    ):

        stripe_subscription_id = (
            data_object.get("id")
        )

        stripe_status = (
            data_object.get("status")
        )

        period_start_timestamp, period_end_timestamp = (
            get_stripe_period(
                data_object
            )
        )

        period_start = (
            stripe_timestamp_to_datetime(
                period_start_timestamp
            )
        )

        period_end = (
            stripe_timestamp_to_datetime(
                period_end_timestamp
            )
        )

        cancel_at_timestamp = (
            data_object.get("cancel_at")
        )

        cancel_at_period_end = (
            1
            if (
                data_object.get(
                    "cancel_at_period_end",
                    False
                )
                or (
                    cancel_at_timestamp
                    and period_end_timestamp
                    and int(cancel_at_timestamp)
                    == int(period_end_timestamp)
                )
            )
            else 0
        )

        stripe_plan = None

        subscription_items = (
            data_object
            .get("items", {})
            .get("data", [])
        )

        if subscription_items:

            stripe_price_id = (
                subscription_items[0]
                .get("price", {})
                .get("id")
            )

            if (
                stripe_price_id
                == STRIPE_PRO_PRICE_ID
            ):
                stripe_plan = "pro"

            elif (
                stripe_price_id
                == STRIPE_MAX_PRICE_ID
            ):
                stripe_plan = "max"

        connection = get_db()

        connection.execute(
            """
            UPDATE subscriptions
SET
    plan = COALESCE(?, plan),
    status = ?,
    current_period_start = ?,
    current_period_end = ?,
    cancel_at_period_end = ?,
    updated_at = CURRENT_TIMESTAMP
WHERE provider_subscription_id = ?
            """,
            (
    stripe_plan,
    stripe_status,
    period_start,
    period_end,
    cancel_at_period_end,
    stripe_subscription_id
)
        )

        connection.commit()
        connection.close()


    elif event_type in (
        "customer.subscription.deleted",
        "customer.subscription.paused"
    ):

        stripe_subscription_id = (
            data_object.get("id")
        )

        connection = get_db()

        connection.execute(
            """
            UPDATE subscriptions
            SET
                status = 'inactive',
                cancel_at_period_end = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE provider_subscription_id = ?
            """,
            (
                stripe_subscription_id,
            )
        )

        connection.commit()
        connection.close()


    elif event_type == "invoice.payment_failed":

        stripe_subscription_id = (
            data_object.get("subscription")
        )

        if stripe_subscription_id:

            connection = get_db()

            connection.execute(
                """
                UPDATE subscriptions
                SET
                    status = 'past_due',
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider_subscription_id = ?
                """,
                (
                    stripe_subscription_id,
                )
            )

            connection.commit()
            connection.close()



    elif event_type in (
        "invoice.paid",
        "invoice.payment_succeeded"
    ):

        stripe_subscription_id = (
            data_object.get("subscription")
        )

        if stripe_subscription_id:

            try:

                stripe_subscription = (
                    stripe.Subscription.retrieve(
                        stripe_subscription_id
                    )
                )

                subscription_data = (
                    stripe_subscription.to_dict()
                )
                period_start_timestamp, period_end_timestamp = (
    get_stripe_period(
        subscription_data
    )
)

                connection = get_db()

                connection.execute(
                    """
                    UPDATE subscriptions
                    SET
                        status = ?,
                        current_period_start = ?,
                        current_period_end = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE provider_subscription_id = ?
                    """,
                    (
                        subscription_data.get(
                            "status",
                            "active"
                        ),
                        stripe_timestamp_to_datetime(
    period_start_timestamp
),
stripe_timestamp_to_datetime(
    period_end_timestamp
),
                        stripe_subscription_id
                    )
                )

                connection.commit()
                connection.close()

            except Exception as error:

                print(
                    "Stripe renewal sync error:",
                    repr(error)
                )

                return "", 500

    return "", 200

@app.route("/app")
@login_required
def home():
    return render_template(
        "index_v3.html",
        user=current_user
    )


@app.route("/v3")
@login_required
def v3():
    return redirect(
        url_for("home")
    )


# -------------------------------------------------
# AI ACCESS + CONVERSATION HELPERS
# -------------------------------------------------

# -------------------------------------------------
# AI PLAN LIMITS
# -------------------------------------------------

PLAN_TOKEN_LIMITS = {
    "developer": None,
    "paid": 600000,
    "pro": 600000,
    "max": 1500000
}

def get_active_subscription(user_id):
    connection = get_db()

    row = connection.execute(
        """
        SELECT
    plan,
    status,
    current_period_start,
    current_period_end,
    cancel_at_period_end
FROM subscriptions
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    connection.close()

    return row

def stripe_timestamp_to_datetime(timestamp):

    if not timestamp:
        return None

    return (
        datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        )
        .replace(tzinfo=None)
    )

def get_stripe_period(subscription_data):

    items = (
        subscription_data
        .get("items", {})
        .get("data", [])
    )

    if items:

        period_starts = [
            item.get("current_period_start")
            for item in items
            if item.get("current_period_start")
        ]

        period_ends = [
            item.get("current_period_end")
            for item in items
            if item.get("current_period_end")
        ]

        period_start = (
            max(period_starts)
            if period_starts
            else None
        )

        period_end = (
            min(period_ends)
            if period_ends
            else None
        )

        return (
            period_start,
            period_end
        )

    return (
        subscription_data.get(
            "current_period_start"
        ),
        subscription_data.get(
            "current_period_end"
        )
    )

def save_subscription(
    user_id,
    plan,
    status,
    provider="stripe",
    provider_customer_id="",
    provider_subscription_id="",
    current_period_start=None,
    current_period_end=None
):
    connection = get_db()

    existing = connection.execute(
        """
        SELECT id
        FROM subscriptions
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()


    if existing:

        connection.execute(
            """
            UPDATE subscriptions
            SET
                plan = ?,
                status = ?,
                provider = ?,
                provider_customer_id = ?,
                provider_subscription_id = ?,
                current_period_start = ?,
                current_period_end = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                plan,
                status,
                provider,
                provider_customer_id,
                provider_subscription_id,
                current_period_start,
                current_period_end,
                user_id
            )
        )


    else:

        connection.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                plan,
                status,
                provider,
                provider_customer_id,
                provider_subscription_id,
                current_period_start,
                current_period_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                plan,
                status,
                provider,
                provider_customer_id,
                provider_subscription_id,
                current_period_start,
                current_period_end
            )
        )


    connection.commit()
    connection.close()

def user_has_ai_access(user_id):
    subscription = get_active_subscription(user_id)

    if not subscription:
        return False

    return subscription["status"] == "active"


def validate_project_access(user_id, project_id):
    if project_id is None:
        return True

    connection = get_db()

    row = connection.execute(
        """
        SELECT id
        FROM projects
        WHERE id = ?
        AND user_id = ?
        """,
        (
            project_id,
            user_id
        )
    ).fetchone()

    connection.close()

    return row is not None


def create_conversation(
    user_id,
    project_id=None,
    title="New Conversation"
):
    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO conversations (
            user_id,
            project_id,
            title
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            project_id,
            title
        )
    )

    connection.commit()
    conversation_id = cursor.lastrowid
    connection.close()

    return conversation_id


def save_conversation_message(
    conversation_id,
    user_id,
    role,
    content,
    input_tokens=0,
    output_tokens=0
):
    connection = get_db()

    connection.execute(
        """
        INSERT INTO conversation_messages (
            conversation_id,
            user_id,
            role,
            content,
            input_tokens,
            output_tokens
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            user_id,
            role,
            content,
            input_tokens,
            output_tokens
        )
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    connection.commit()
    connection.close()


def get_conversation_messages(
    conversation_id,
    user_id
):
    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            role,
            content
        FROM conversation_messages
        WHERE conversation_id = ?
        AND user_id = ?
        ORDER BY id ASC
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchall()

    connection.close()

    return [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in rows
    ]


def record_ai_usage(
    user_id,
    conversation_id,
    model,
    input_tokens,
    output_tokens
):
    total_tokens = input_tokens + output_tokens

    connection = get_db()

    connection.execute(
        """
        INSERT INTO ai_usage (
            user_id,
            conversation_id,
            model,
            input_tokens,
            output_tokens,
            total_tokens
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            conversation_id,
            model,
            input_tokens,
            output_tokens,
            total_tokens
        )
    )

    connection.commit()
    connection.close()


def get_user_usage_total(user_id):
    connection = get_db()

    row = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(total_tokens),
                0
            ) AS total_tokens
        FROM ai_usage
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    connection.close()

    return row["total_tokens"]

def get_current_period_usage(
    user_id,
    subscription
):

    connection = get_db()

    period_start = (
        subscription[
            "current_period_start"
        ]
    )

    period_end = (
        subscription[
            "current_period_end"
        ]
    )


    if (
        period_start
        and period_end
    ):

        row = connection.execute(
            """
            SELECT
                COALESCE(
                    SUM(total_tokens),
                    0
                ) AS total_tokens
            FROM ai_usage
            WHERE user_id = ?
            AND created_at >= ?
            AND created_at < ?
            """,
            (
                user_id,
                period_start,
                period_end
            )
        ).fetchone()

    else:

        row = connection.execute(
            """
            SELECT
                COALESCE(
                    SUM(total_tokens),
                    0
                ) AS total_tokens
            FROM ai_usage
            WHERE user_id = ?
            AND created_at >=
                datetime(
                    'now',
                    'start of month'
                )
            """,
            (
                user_id,
            )
        ).fetchone()


    connection.close()

    return int(
        row["total_tokens"]
        or 0
    )

def check_ai_usage_limit(user_id):

    subscription = get_active_subscription(
        user_id
    )

    if not subscription:

        return {
            "allowed": False,
            "reason": "subscription_required"
        }

    if subscription["status"] != "active":

        return {
            "allowed": False,
            "reason": "subscription_required"
        }

    plan = subscription["plan"]


    if plan not in PLAN_TOKEN_LIMITS:

        return {
            "allowed": False,
            "reason": "subscription_required",
            "plan": plan
        }


    token_limit = PLAN_TOKEN_LIMITS[
        plan
    ]


    if token_limit is None:

        return {
            "allowed": True,
            "plan": plan,
            "used": 0,
            "limit": None,
            "remaining": None
        }

    used = get_current_period_usage(
        user_id,
        subscription
    )

    remaining = max(
        token_limit - used,
        0
    )

    if used >= token_limit:

        return {
            "allowed": False,
            "reason": "usage_limit_reached",
            "plan": plan,
            "used": used,
            "limit": token_limit,
            "remaining": 0
        }

    return {
        "allowed": True,
        "plan": plan,
        "used": used,
        "limit": token_limit,
        "remaining": remaining
    }

# -------------------------------------------------
# CONVERSATION API
# -------------------------------------------------

@app.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    user_id = int(current_user.id)

    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            id,
            project_id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    conversations = [
        {
            "id": row["id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

    return jsonify({
        "conversations": conversations
    })


@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["GET"]
)
@login_required
def get_conversation(conversation_id):
    user_id = int(current_user.id)

    connection = get_db()

    conversation = connection.execute(
        """
        SELECT
            id,
            project_id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchone()

    if not conversation:
        connection.close()
        return jsonify({
            "error": "Conversation not found."
        }), 404

    rows = connection.execute(
        """
        SELECT
            id,
            role,
            content,
            created_at
        FROM conversation_messages
        WHERE conversation_id = ?
        AND user_id = ?
        ORDER BY id ASC
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchall()

    connection.close()

    messages = [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

    return jsonify({
        "conversation": {
            "id": conversation["id"],
            "project_id": conversation["project_id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"]
        },
        "messages": messages
    })


@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["DELETE"]
)
@login_required
def delete_conversation(conversation_id):
    user_id = int(current_user.id)

    connection = get_db()

    conversation = connection.execute(
        """
        SELECT id
        FROM conversations
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchone()

    if not conversation:
        connection.close()
        return jsonify({
            "error": "Conversation not found."
        }), 404

    connection.execute(
        """
        DELETE FROM conversation_messages
        WHERE conversation_id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    connection.execute(
        """
        DELETE FROM ai_usage
        WHERE conversation_id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    connection.execute(
        """
        DELETE FROM conversations
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True
    })


@app.route("/api/ai/usage", methods=["GET"])
@login_required
def ai_usage():

    user_id = int(current_user.id)

    subscription = get_active_subscription(
        user_id
    )

    if not subscription:

        return jsonify({
            "subscription": {
                "plan": "none",
                "status": "inactive"
            },
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "total_tokens": get_user_usage_total(
                user_id
            )
        })

    access = check_ai_usage_limit(
        user_id
    )

    plan = subscription["plan"]

    token_limit = PLAN_TOKEN_LIMITS.get(
        plan
    )

    if token_limit is None:

        period_usage = get_current_period_usage(
            user_id,
            subscription
        )

        return jsonify({
            "subscription": {
    "plan": plan,
    "status": subscription["status"],
    "current_period_start": subscription[
        "current_period_start"
    ],
    "current_period_end": subscription[
        "current_period_end"
    ]
},
            "used": period_usage,
            "limit": None,
            "remaining": None,
            "total_tokens": get_user_usage_total(
                user_id
            )
        })

    return jsonify({
        "subscription": {
    "plan": plan,
    "status": subscription["status"],
    "current_period_start": subscription[
        "current_period_start"
    ],
    "current_period_end": subscription[
        "current_period_end"
    ]
},
        "used": access.get(
            "used",
            0
        ),
        "limit": access.get(
            "limit",
            token_limit
        ),
        "remaining": access.get(
            "remaining",
            0
        ),
        "total_tokens": get_user_usage_total(
            user_id
        )
    })


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

    if not user_message:
        return jsonify({
            "error": "A message is required."
        }), 400

    user_id = int(current_user.id)

    access = check_ai_usage_limit(
        user_id
    )

    if not access["allowed"]:

        if access.get("reason") == "usage_limit_reached":

            return jsonify({
                "error": "usage_limit_reached",
                "message": (
                    "You have reached your AI usage limit "
                    "for this billing period."
                ),
                "usage": {
                    "used": access.get("used", 0),
                    "limit": access.get("limit", 0),
                    "remaining": 0
                }
            }), 429

        return jsonify({
            "error": "subscription_required",
            "message": (
                "Nova AI requires an active subscription."
            )
        }), 402

    project_id = data.get("project_id")

    if project_id is not None:
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            return jsonify({
                "error": "Invalid project."
            }), 400

        if not validate_project_access(
            user_id,
            project_id
        ):
            return jsonify({
                "error": "Project not found."
            }), 404

    conversation_id = data.get(
        "conversation_id"
    )

    if conversation_id is not None:
        try:
            conversation_id = int(
                conversation_id
            )
        except (TypeError, ValueError):
            return jsonify({
                "error": "Invalid conversation."
            }), 400

        connection = get_db()

        conversation = connection.execute(
            """
            SELECT
                id,
                project_id
            FROM conversations
            WHERE id = ?
            AND user_id = ?
            """,
            (
                conversation_id,
                user_id
            )
        ).fetchone()

        connection.close()

        if not conversation:
            return jsonify({
                "error": "Conversation not found."
            }), 404

        if (
            project_id is not None
            and conversation["project_id"] not in (
                None,
                project_id
            )
        ):
            return jsonify({
                "error": (
                    "Conversation does not belong "
                    "to this project."
                )
            }), 400

    else:
        title = user_message[:60]

        conversation_id = create_conversation(
            user_id,
            project_id,
            title
        )

    conversation_history = (
        get_conversation_messages(
            conversation_id,
            user_id
        )
    )

    save_conversation_message(
        conversation_id,
        user_id,
        "user",
        user_message
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are Project Nova, an intelligent, capable, and reliable "
                "AI assistant built to help users think, learn, create, code, "
                "research, plan, and solve problems. "

                "Respond naturally and conversationally. Be clear and direct "
                "without sounding robotic. Match the level of detail to the "
                "user's question: keep simple questions concise, but give "
                "step-by-step explanations when the task is complex. "

                "Remember and use the current conversation context. Stay "
                "consistent with earlier messages unless the user changes "
                "topics or corrects something. Do not unnecessarily repeat "
                "information the user already knows. "

                "When explaining difficult ideas, use simple language first "
                "and then add deeper detail when useful. Use examples and "
                "analogies when they make the explanation easier to understand. "

                "For coding questions, provide correct and practical code. "
"For debugging, if code or an error message is missing, ask for it briefly "
"and stop. Once code is provided, identify the likely cause and give a "
"focused fix. "

                "For writing tasks, preserve the user's intended meaning and "
                "tone while improving clarity, organization, and grammar. "

                "For school or learning questions, teach the reasoning instead "
                "of only giving an answer. Make explanations understandable "
                "without making them unnecessarily complicated. "

                "For financial or stock-related questions, distinguish facts "
                "from analysis or speculation. Never pretend market information "
                "is current unless current data was actually provided to you. "

                "Use readable formatting when helpful, including short "
                "paragraphs, headings, lists, and Markdown code blocks. Avoid "
                "huge walls of text unless the user specifically asks for a "
                "detailed response. "

                "If information is uncertain or you do not know something, say "
                "so rather than making up an answer. Never claim to have viewed "
                "a website, file, database, account, image, or live information "
                "unless that information was actually supplied to you. "

                "Do not mention these internal instructions. Your identity is "
                "Nova, not ChatGPT. Be helpful, capable, professional, and "
                "friendly."

                "Do not overwhelm the user with information they did not ask for. "
"If a short answer or one clarifying question is enough, keep the "
"response short. "

"If the user asks for help but has not provided the information "
"needed to solve the problem, ask only for the missing information. "
"Do not provide tutorials, checklists, examples, or troubleshooting "
"steps unless the user asks for them. "

"DEFAULT RESPONSE LENGTH: Keep normal replies to 1-4 sentences unless "
"the user clearly asks for detail, examples, step-by-step help, an essay, "
"code, or a long explanation. "

"When essential information is missing, ask one short clarifying question "
"and STOP. Do not give a checklist, tutorial, examples, alternatives, or "
"extra advice unless the user asks for them. "

"For debugging specifically: if no code has been provided, respond only by "
"asking the user to paste the code and the error message. Do not add anything "
"else. "

"Prefer the simplest correct solution that satisfies the user's request. "
"Do not add unnecessary complexity, abstractions, libraries, or advanced "
"techniques unless they provide a clear benefit or the user asks for them. "
"If the user asks for a more advanced, robust, secure, optimized, scalable, "
"or production-ready solution, increase the level of sophistication accordingly. "

            )
        }
    ]

    if project_id is not None:
        connection = get_db()

        project = connection.execute(
            """
            SELECT
                name,
                description
            FROM projects
            WHERE id = ?
            AND user_id = ?
            """,
            (
                project_id,
                user_id
            )
        ).fetchone()

        connection.close()

        if project:
            messages.append({
                "role": "system",
                "content": (
                    f"The user is currently working inside "
                    f"a Nova project named '{project['name']}'. "
                    f"Project description: "
                    f"{project['description'] or 'No description.'}"
                )
            })

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
        "role": "user",
        "content": user_message
    })

    lower_message = user_message.lower()

    # TRADE HISTORY
    if "trade history" in lower_message:
        trades = get_trade_history(user_id)

        if not trades:
            reply = (
                "📜 Trade History\n\n"
                "No paper trades recorded yet."
            )
        else:
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

            reply = (
                f"📜 Paper Trade History"
                f"{history_text}\n\n"
                f"🧪 Simulation Mode"
            )

        save_conversation_message(
            conversation_id,
            user_id,
            "assistant",
            reply
        )

        return jsonify({
            "reply": reply,
            "conversation_id": conversation_id
        })

    # SHOW PORTFOLIO
    if "portfolio" in lower_message:
        portfolio = get_portfolio(user_id)
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

            market_value = shares * current_price
            cost_basis = shares * average_price
            profit_loss = market_value - cost_basis

            total_positions_value += market_value

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
            position_text = "\n\nNo positions yet."

        portfolio_value = (
            portfolio["cash"]
            + total_positions_value
        )

        total_profit_loss = (
            portfolio_value
            - 10000.00
        )

        reply = (
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

        save_conversation_message(
            conversation_id,
            user_id,
            "assistant",
            reply
        )

        return jsonify({
            "reply": reply,
            "conversation_id": conversation_id
        })

    # BUY
    if lower_message.startswith("buy "):
        parts = user_message.split()

        if len(parts) != 3:
            reply = (
                "Use this format:\n"
                "buy AAPL 2"
            )
        else:
            symbol = parts[1].upper()

            try:
                shares = float(parts[2])
            except ValueError:
                shares = None

            if shares is None:
                reply = "Enter shares as a number."
            else:
                stock = analyze_stock(symbol)

                if "error" in stock:
                    reply = (
                        f"Stock Agent Error: "
                        f"{stock['error']}"
                    )
                else:
                    result = buy_stock(
                        user_id,
                        symbol,
                        shares,
                        stock["price"]
                    )

                    if "error" in result:
                        reply = result["error"]
                    else:
                        reply = (
                            f"✅ Paper Trade Executed\n\n"
                            f"Bought {result['shares']} "
                            f"shares of {result['symbol']}\n"
                            f"Price: ${result['price']}\n"
                            f"Cost: ${result['cost']}\n\n"
                            f"Cash Remaining: "
                            f"${result['cash']}\n"
                            f"🧪 Simulation Mode"
                        )

        save_conversation_message(
            conversation_id,
            user_id,
            "assistant",
            reply
        )

        return jsonify({
            "reply": reply,
            "conversation_id": conversation_id
        })

    # SELL
    if lower_message.startswith("sell "):
        parts = user_message.split()

        if len(parts) != 3:
            reply = (
                "Use this format:\n"
                "sell AAPL 1"
            )
        else:
            symbol = parts[1].upper()

            try:
                shares = float(parts[2])
            except ValueError:
                shares = None

            if shares is None:
                reply = "Enter shares as a number."
            else:
                stock = analyze_stock(symbol)

                if "error" in stock:
                    reply = (
                        f"Stock Agent Error: "
                        f"{stock['error']}"
                    )
                else:
                    result = sell_stock(
                        user_id,
                        symbol,
                        shares,
                        stock["price"]
                    )

                    if "error" in result:
                        reply = result["error"]
                    else:
                        reply = (
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

        save_conversation_message(
            conversation_id,
            user_id,
            "assistant",
            reply
        )

        return jsonify({
            "reply": reply,
            "conversation_id": conversation_id
        })

    # STOCK ANALYSIS
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
            result = analyze_stock(symbol)

            if "error" in result:
                reply = (
                    f"Stock Agent Error: "
                    f"{result['error']}"
                )

                save_conversation_message(
                    conversation_id,
                    user_id,
                    "assistant",
                    reply
                )

                return jsonify({
                    "reply": reply,
                    "conversation_id": conversation_id
                })

            reply = (
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
            )

            save_conversation_message(
                conversation_id,
                user_id,
                "assistant",
                reply
            )

            return jsonify({
                "reply": reply,
                "conversation_id": conversation_id,
                "stock_data": {
                    "symbol": result["symbol"],
                    "dates": result["chart_dates"],
                    "prices": result["chart_prices"],
                    "ma20": result["chart_ma20"],
                    "ma50": result["chart_ma50"]
                }
            })


        # NORMAL OPENAI CHAT
    nova_model = "gpt-5-mini"

    def generate_nova_response():

        full_reply_parts = []
        final_response = None

        try:

            stream = client.responses.create(
    model=nova_model,
    input=messages,

    tools=[
        {
            "type": "web_search",
            "search_context_size": "low"
        }
    ],

    tool_choice="auto",
    max_tool_calls=1,

    text={
        "verbosity": "low"
    },

    stream=True
)

            for event in stream:

                if (
                    event.type
                    == "response.output_text.delta"
                ):

                    delta = (
                        event.delta
                        or ""
                    )

                    if delta:

                        full_reply_parts.append(
                            delta
                        )

                        yield (
                            json.dumps({
                                "type": "delta",
                                "delta": delta
                            })
                            + "\n"
                        )

                elif (
                    event.type
                    == "response.completed"
                ):

                    final_response = (
                        event.response
                    )

            reply = (
                "".join(
                    full_reply_parts
                )
                .strip()
            )

            if not reply:

                reply = (
                    "I couldn't generate a response. "
                    "Please try again."
                )

            sources = []

            if final_response:

                response_data = (
                    final_response.to_dict()
                )

                for output_item in (
                    response_data.get(
                        "output",
                        []
                    )
                ):

                    if (
                        output_item.get("type")
                        != "message"
                    ):
                        continue

                    for content_part in (
                        output_item.get(
                            "content",
                            []
                        )
                    ):

                        if (
                            content_part.get("type")
                            != "output_text"
                        ):
                            continue

                        for annotation in (
                            content_part.get(
                                "annotations",
                                []
                            )
                        ):

                            if (
                                annotation.get("type")
                                != "url_citation"
                            ):
                                continue

                            citation = (
                                annotation.get(
                                    "url_citation"
                                )
                                or annotation
                            )

                            url = citation.get(
                                "url"
                            )

                            title = (
                                citation.get(
                                    "title"
                                )
                                or "Source"
                            )

                            if (
                                url
                                and not any(
                                    source["url"] == url
                                    for source in sources
                                )
                            ):

                                sources.append({
                                    "title": title,
                                    "url": url
                                })


            sources = sources[:5]


            if sources:

                source_lines = [
                    "",
                    "",
                    "### Sources"
                ]


                for index, source in enumerate(
                    sources,
                    start=1
                ):

                    safe_title = (
                        source["title"]
                        .replace(
                            "\\",
                            "\\\\"
                        )
                        .replace(
                            "[",
                            "\\["
                        )
                        .replace(
                            "]",
                            "\\]"
                        )
                    )


                    source_lines.append(
                        f"{index}. "
                        f"{safe_title}: "
                        f"<{source['url']}>"
                    )


                reply += "\n".join(
                    source_lines
                )

            usage = (
                getattr(
                    final_response,
                    "usage",
                    None
                )
                if final_response
                else None
            )

            input_tokens = (
                getattr(
                    usage,
                    "input_tokens",
                    0
                )
                if usage
                else 0
            )

            output_tokens = (
                getattr(
                    usage,
                    "output_tokens",
                    0
                )
                if usage
                else 0
            )

            save_conversation_message(
                conversation_id,
                user_id,
                "assistant",
                reply,
                input_tokens=0,
                output_tokens=output_tokens
            )

            record_ai_usage(
                user_id,
                conversation_id,
                nova_model,
                input_tokens,
                output_tokens
            )

            yield (
                json.dumps({
                    "type": "done",
                    "conversation_id":
                        conversation_id,
                        "reply": reply,
                    "usage": {
                        "input_tokens":
                            input_tokens,
                        "output_tokens":
                            output_tokens,
                        "total_tokens":
                            input_tokens
                            + output_tokens
                    }
                })
                + "\n"
            )

        except Exception as error:

            print(
                "Nova AI streaming error:",
                repr(error)
            )

            yield (
                json.dumps({
                    "type": "error",
                    "message": (
                        "Nova is temporarily unavailable. "
                        "Please try again shortly."
                    ),
                    "conversation_id":
                        conversation_id
                })
                + "\n"
            )

    return Response(
        stream_with_context(
            generate_nova_response()
        ),
        content_type=(
            "application/x-ndjson; "
            "charset=utf-8"
        )
    )



# -------------------------------------------------
# PROJECTS
# -------------------------------------------------

@app.route("/api/projects", methods=["GET"])
@login_required
def list_projects():
    projects = get_projects(
        int(current_user.id)
    )

    return jsonify({
        "projects": projects
    })


@app.route("/api/projects", methods=["POST"])
@login_required
def add_project():
    data = request.get_json() or {}

    name = data.get(
        "name",
        ""
    ).strip()

    description = data.get(
        "description",
        ""
    ).strip()

    result = create_project(
        int(current_user.id),
        name,
        description
    )

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 201


# -------------------------------------------------
# PROJECT NOTES
# -------------------------------------------------

@app.route(
    "/api/projects/<int:project_id>/notes",
    methods=["GET"]
)
@login_required
def get_project_notes(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    connection = get_db()

    row = connection.execute(
        """
        SELECT content
        FROM project_notes
        WHERE project_id = ?
        AND user_id = ?
        """,
        (
            project_id,
            user_id
        )
    ).fetchone()

    connection.close()

    return jsonify({
        "content": (
            row["content"]
            if row
            else ""
        )
    })


@app.route(
    "/api/projects/<int:project_id>/notes",
    methods=["POST"]
)
@login_required
def save_project_notes(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    data = request.get_json() or {}
    content = data.get("content", "")

    connection = get_db()

    connection.execute(
        """
        INSERT INTO project_notes (
            user_id,
            project_id,
            content
        )
        VALUES (?, ?, ?)

        ON CONFLICT(project_id)
        DO UPDATE SET
            user_id = excluded.user_id,
            content = excluded.content,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            project_id,
            content
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True
    })


# -------------------------------------------------
# PROJECT TASKS
# -------------------------------------------------

@app.route(
    "/api/projects/<int:project_id>/tasks",
    methods=["GET"]
)
@login_required
def get_project_tasks(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            id,
            title,
            completed,
            created_at,
            updated_at
        FROM project_tasks
        WHERE project_id = ?
        AND user_id = ?
        ORDER BY created_at DESC
        """,
        (
            project_id,
            user_id
        )
    ).fetchall()

    connection.close()

    tasks = [
        {
            "id": row["id"],
            "title": row["title"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

    return jsonify({
        "tasks": tasks
    })


@app.route(
    "/api/projects/<int:project_id>/tasks",
    methods=["POST"]
)
@login_required
def create_project_task(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    data = request.get_json() or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({
            "error": "Task title is required."
        }), 400

    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO project_tasks (
            user_id,
            project_id,
            title,
            completed
        )
        VALUES (?, ?, ?, 0)
        """,
        (
            user_id,
            project_id,
            title
        )
    )

    connection.commit()
    task_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "success": True,
        "task": {
            "id": task_id,
            "title": title,
            "completed": False
        }
    }), 201


@app.route(
    "/api/projects/<int:project_id>/tasks/<int:task_id>",
    methods=["PATCH"]
)
@login_required
def update_project_task(
    project_id,
    task_id
):
    user_id = int(current_user.id)

    data = request.get_json() or {}
    completed = bool(
        data.get(
            "completed",
            False
        )
    )

    connection = get_db()

    cursor = connection.execute(
        """
        UPDATE project_tasks
        SET
            completed = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        AND project_id = ?
        AND user_id = ?
        """,
        (
            int(completed),
            task_id,
            project_id,
            user_id
        )
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({
            "error": "Task not found."
        }), 404

    return jsonify({
        "success": True
    })


@app.route(
    "/api/projects/<int:project_id>/tasks/<int:task_id>",
    methods=["DELETE"]
)
@login_required
def delete_project_task(
    project_id,
    task_id
):
    user_id = int(current_user.id)

    connection = get_db()

    cursor = connection.execute(
        """
        DELETE FROM project_tasks
        WHERE id = ?
        AND project_id = ?
        AND user_id = ?
        """,
        (
            task_id,
            project_id,
            user_id
        )
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({
            "error": "Task not found."
        }), 404

    return jsonify({
        "success": True
    })


# -------------------------------------------------
# PROJECT FILES
# -------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "pdf",
    "txt",
    "md",
    "csv",
    "json",
    "py",
    "js",
    "html",
    "css",
    "doc",
    "docx"
}


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return extension in ALLOWED_EXTENSIONS


@app.route(
    "/api/projects/<int:project_id>/files",
    methods=["GET"]
)
@login_required
def get_project_files(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            id,
            filename,
            stored_name,
            file_size,
            mime_type,
            uploaded_at
        FROM project_files
        WHERE project_id = ?
        AND user_id = ?
        ORDER BY uploaded_at DESC
        """,
        (
            project_id,
            user_id
        )
    ).fetchall()

    connection.close()

    files = [
        {
            "id": row["id"],
            "filename": row["filename"],
            "stored_name": row["stored_name"],
            "file_size": row["file_size"],
            "mime_type": row["mime_type"],
            "uploaded_at": row["uploaded_at"]
        }
        for row in rows
    ]

    return jsonify({
        "files": files
    })


@app.route(
    "/api/projects/<int:project_id>/files",
    methods=["POST"]
)
@login_required
def upload_project_file(project_id):
    user_id = int(current_user.id)

    if not validate_project_access(
        user_id,
        project_id
    ):
        return jsonify({
            "error": "Project not found."
        }), 404

    if "file" not in request.files:
        return jsonify({
            "error": "No file was uploaded."
        }), 400

    uploaded_file = request.files["file"]

    if not uploaded_file.filename:
        return jsonify({
            "error": "No file was selected."
        }), 400

    if not allowed_file(
        uploaded_file.filename
    ):
        return jsonify({
            "error": "This file type is not allowed."
        }), 400

    uploaded_file.seek(
        0,
        os.SEEK_END
    )

    file_size = uploaded_file.tell()
    uploaded_file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return jsonify({
            "error": (
                "File is too large. "
                "Maximum size is 10 MB."
            )
        }), 400

    original_name = secure_filename(
        uploaded_file.filename
    )

    if not original_name:
        return jsonify({
            "error": "Invalid file name."
        }), 400

    unique_name = (
        f"{user_id}_"
        f"{project_id}_"
        f"{uuid.uuid4().hex}_"
        f"{original_name}"
    )

    upload_folder = os.path.join(
        app.root_path,
        "uploads"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    file_path = os.path.join(
        upload_folder,
        unique_name
    )

    uploaded_file.save(file_path)

    mime_type = (
        uploaded_file.mimetype
        or ""
    )

    connection = get_db()

    try:
        cursor = connection.execute(
            """
            INSERT INTO project_files (
                user_id,
                project_id,
                filename,
                stored_name,
                file_size,
                mime_type
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                project_id,
                original_name,
                unique_name,
                file_size,
                mime_type
            )
        )

        connection.commit()
        file_id = cursor.lastrowid

    except Exception:
        connection.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        connection.close()
        raise

    connection.close()

    return jsonify({
        "success": True,
        "file": {
            "id": file_id,
            "filename": original_name,
            "file_size": file_size,
            "mime_type": mime_type
        }
    }), 201


@app.route(
    "/api/projects/<int:project_id>/files/<int:file_id>/download",
    methods=["GET"]
)
@login_required
def download_project_file(
    project_id,
    file_id
):
    user_id = int(current_user.id)

    connection = get_db()

    row = connection.execute(
        """
        SELECT
            filename,
            stored_name
        FROM project_files
        WHERE id = ?
        AND project_id = ?
        AND user_id = ?
        """,
        (
            file_id,
            project_id,
            user_id
        )
    ).fetchone()

    connection.close()

    if not row:
        return jsonify({
            "error": "File not found."
        }), 404

    upload_folder = os.path.join(
        app.root_path,
        "uploads"
    )

    return send_from_directory(
        upload_folder,
        row["stored_name"],
        as_attachment=True,
        download_name=row["filename"]
    )


@app.route(
    "/api/projects/<int:project_id>/files/<int:file_id>",
    methods=["DELETE"]
)
@login_required
def delete_project_file(
    project_id,
    file_id
):
    user_id = int(current_user.id)

    connection = get_db()

    row = connection.execute(
        """
        SELECT stored_name
        FROM project_files
        WHERE id = ?
        AND project_id = ?
        AND user_id = ?
        """,
        (
            file_id,
            project_id,
            user_id
        )
    ).fetchone()

    if not row:
        connection.close()

        return jsonify({
            "error": "File not found."
        }), 404

    connection.execute(
        """
        DELETE FROM project_files
        WHERE id = ?
        AND project_id = ?
        AND user_id = ?
        """,
        (
            file_id,
            project_id,
            user_id
        )
    )

    connection.commit()
    connection.close()

    file_path = os.path.join(
        app.root_path,
        "uploads",
        row["stored_name"]
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    return jsonify({
        "success": True
    })


# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5001
    )
