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
            VALUES (?, ?)
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


def buy_stock(user_id, symbol, shares, price):
    symbol = symbol.upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        return {
            "error": "Shares must be greater than zero."
        }

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
            VALUES (?, ?)
            """,
            (
                user_id,
                STARTING_CASH
            )
        )

        cash = STARTING_CASH

    else:
        cash = portfolio_row["cash"]

    cost = shares * price

    if cost > cash:
        connection.close()

        return {
            "error": "Not enough simulated cash."
        }

    position = connection.execute(
        """
        SELECT
            shares,
            average_price
        FROM positions
        WHERE user_id = ?
        AND symbol = ?
        """,
        (
            user_id,
            symbol
        )
    ).fetchone()

    if position:
        old_shares = position["shares"]
        old_average = position["average_price"]

        total_shares = old_shares + shares

        new_average = (
            (old_shares * old_average)
            + (shares * price)
        ) / total_shares

        connection.execute(
            """
            UPDATE positions
            SET
                shares = ?,
                average_price = ?
            WHERE user_id = ?
            AND symbol = ?
            """,
            (
                total_shares,
                round(new_average, 2),
                user_id,
                symbol
            )
        )

    else:
        connection.execute(
            """
            INSERT INTO positions (
                user_id,
                symbol,
                shares,
                average_price
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                symbol,
                shares,
                round(price, 2)
            )
        )

    new_cash = round(
        cash - cost,
        2
    )

    connection.execute(
        """
        UPDATE portfolios
        SET cash = ?
        WHERE user_id = ?
        """,
        (
            new_cash,
            user_id
        )
    )

    connection.execute(
        """
        INSERT INTO trades (
            user_id,
            action,
            symbol,
            shares,
            price,
            total,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "BUY",
            symbol,
            shares,
            round(price, 2),
            round(cost, 2),
            datetime.now().strftime(
                "%Y-%m-%d %I:%M:%S %p"
            )
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "cost": round(cost, 2),
        "cash": new_cash
    }


def sell_stock(user_id, symbol, shares, price):
    symbol = symbol.upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        return {
            "error": "Shares must be greater than zero."
        }

    connection = get_db()

    position = connection.execute(
        """
        SELECT
            shares,
            average_price
        FROM positions
        WHERE user_id = ?
        AND symbol = ?
        """,
        (
            user_id,
            symbol
        )
    ).fetchone()

    if not position:
        connection.close()

        return {
            "error": f"You do not own {symbol}."
        }

    owned_shares = position["shares"]

    if shares > owned_shares:
        connection.close()

        return {
            "error": "You do not own that many shares."
        }

    portfolio_row = connection.execute(
        """
        SELECT cash
        FROM portfolios
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    cash = (
        portfolio_row["cash"]
        if portfolio_row
        else STARTING_CASH
    )

    proceeds = shares * price
    remaining_shares = owned_shares - shares

    if remaining_shares == 0:
        connection.execute(
            """
            DELETE FROM positions
            WHERE user_id = ?
            AND symbol = ?
            """,
            (
                user_id,
                symbol
            )
        )

    else:
        connection.execute(
            """
            UPDATE positions
            SET shares = ?
            WHERE user_id = ?
            AND symbol = ?
            """,
            (
                remaining_shares,
                user_id,
                symbol
            )
        )

    new_cash = round(
        cash + proceeds,
        2
    )

    connection.execute(
        """
        UPDATE portfolios
        SET cash = ?
        WHERE user_id = ?
        """,
        (
            new_cash,
            user_id
        )
    )

    connection.execute(
        """
        INSERT INTO trades (
            user_id,
            action,
            symbol,
            shares,
            price,
            total,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "SELL",
            symbol,
            shares,
            round(price, 2),
            round(proceeds, 2),
            datetime.now().strftime(
                "%Y-%m-%d %I:%M:%S %p"
            )
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "proceeds": round(proceeds, 2),
        "cash": new_cash
    }