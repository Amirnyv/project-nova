from datetime import datetime

from database import get_db


STARTING_CASH = 10000.00


def get_portfolio(user_id):
    connection = get_db()

    portfolio_row = connection.execute(
        """
        SELECT cash
        FROM portfolios
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    if portfolio_row is None:
        connection.execute(
            """
            INSERT INTO portfolios (
                user_id,
                cash
            )
            VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING
            """,
            (
                user_id,
                STARTING_CASH
            )
        )

        connection.commit()

        cash = STARTING_CASH

    else:
        cash = portfolio_row["cash"]

    position_rows = connection.execute(
        """
        SELECT
            symbol,
            shares,
            average_price
        FROM positions
        WHERE user_id = ?
        ORDER BY symbol
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    positions = {}

    for row in position_rows:
        positions[row["symbol"]] = {
            "shares": row["shares"],
            "average_price": row["average_price"]
        }

    return {
        "cash": cash,
        "positions": positions
    }


def get_trade_history(user_id):
    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            action,
            symbol,
            shares,
            price,
            total,
            created_at
        FROM trades
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    trades = []

    for row in rows:
        trades.append({
            "action": row["action"],
            "symbol": row["symbol"],
            "shares": row["shares"],
            "price": row["price"],
            "total": row["total"],
            "timestamp": row["created_at"]
        })

    return trades


def _trade(user_id, symbol, shares, price, side):
    # Chat and the native API serialize mutations on the same user/account.
    from database import USE_POSTGRES
    from services.paper_trading import PaperTrading, PaperError
    try:
        result = PaperTrading(get_db, USE_POSTGRES).legacy_trade(user_id, symbol, shares, price, side)
    except PaperError as error:
        return {"error": error.message}
    return {"success": True, "symbol": result["symbol"], "shares": float(result["shares"]),
            "price": float(result["price"]), "cash": float(result["cash"]),
            "cost" if side == "BUY" else "proceeds": float(result["total"])}


def buy_stock(user_id, symbol, shares, price):
    return _trade(user_id, symbol, shares, price, "BUY")


def sell_stock(user_id, symbol, shares, price):
    return _trade(user_id, symbol, shares, price, "SELL")
