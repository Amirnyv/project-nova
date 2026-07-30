import json
import os
from datetime import datetime

STARTING_CASH = 10000.00

DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "portfolio_data.json"
)


def default_portfolio():
    return {
        "cash": STARTING_CASH,
        "positions": {},
        "trade_history": []
    }


def load_portfolio():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as file:
                data = json.load(file)

                # Backward compatibility with your old save file
                if "trade_history" not in data:
                    data["trade_history"] = []

                return data

        except (json.JSONDecodeError, OSError):
            pass

    return default_portfolio()


def save_portfolio():
    with open(DATA_FILE, "w") as file:
        json.dump(portfolio, file, indent=4)


def record_trade(action, symbol, shares, price):
    trade = {
        "action": action,
        "symbol": symbol,
        "shares": shares,
        "price": round(price, 2),
        "total": round(shares * price, 2),
        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %I:%M:%S %p"
        )
    }

    portfolio["trade_history"].append(trade)


portfolio = load_portfolio()


def get_portfolio():
    return portfolio


def get_trade_history():
    return portfolio["trade_history"]


def buy_stock(symbol, shares, price):
    symbol = symbol.upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        return {
            "error": "Shares must be greater than zero."
        }

    cost = shares * price

    if cost > portfolio["cash"]:
        return {
            "error": "Not enough simulated cash."
        }

    position = portfolio["positions"].get(symbol)

    if position:
        old_shares = position["shares"]
        old_average = position["average_price"]

        total_shares = old_shares + shares

        new_average = (
            (old_shares * old_average) +
            (shares * price)
        ) / total_shares

        position["shares"] = total_shares
        position["average_price"] = round(new_average, 2)

    else:
        portfolio["positions"][symbol] = {
            "shares": shares,
            "average_price": round(price, 2)
        }

    portfolio["cash"] = round(
        portfolio["cash"] - cost,
        2
    )

    record_trade(
        "BUY",
        symbol,
        shares,
        price
    )

    save_portfolio()

    return {
        "success": True,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "cost": round(cost, 2),
        "cash": portfolio["cash"]
    }


def sell_stock(symbol, shares, price):
    symbol = symbol.upper()
    shares = float(shares)
    price = float(price)

    position = portfolio["positions"].get(symbol)

    if not position:
        return {
            "error": f"You do not own {symbol}."
        }

    if shares <= 0:
        return {
            "error": "Shares must be greater than zero."
        }

    if shares > position["shares"]:
        return {
            "error": "You do not own that many shares."
        }

    proceeds = shares * price

    position["shares"] -= shares

    if position["shares"] == 0:
        del portfolio["positions"][symbol]

    portfolio["cash"] = round(
        portfolio["cash"] + proceeds,
        2
    )

    record_trade(
        "SELL",
        symbol,
        shares,
        price
    )

    save_portfolio()

    return {
        "success": True,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "proceeds": round(proceeds, 2),
        "cash": portfolio["cash"]
    }