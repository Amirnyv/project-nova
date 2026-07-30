STARTING_CASH = 10000.00

portfolio = {
    "cash": STARTING_CASH,
    "positions": {}
}


def get_portfolio():
    return portfolio


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

    return {
        "success": True,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "proceeds": round(proceeds, 2),
        "cash": portfolio["cash"]
    }