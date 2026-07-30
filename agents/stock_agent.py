import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BASE_URL = "https://api.twelvedata.com"


def get_json(endpoint, params):
    params["apikey"] = API_KEY

    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if "code" in data or data.get("status") == "error":
        raise ValueError(
            data.get("message", "Market data request failed.")
        )

    return data


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    changes = [
        prices[i] - prices[i - 1]
        for i in range(1, len(prices))
    ]

    recent_changes = changes[-period:]

    gains = [
        change if change > 0 else 0
        for change in recent_changes
    ]

    losses = [
        abs(change) if change < 0 else 0
        for change in recent_changes
    ]

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss

    return round(
        100 - (100 / (1 + relative_strength)),
        2
    )


def calculate_volatility(prices):
    if len(prices) < 2:
        return 0

    changes = []

    for i in range(1, len(prices)):
        previous = prices[i - 1]

        if previous != 0:
            percent_change = (
                (prices[i] - previous) / previous
            ) * 100

            changes.append(abs(percent_change))

    if not changes:
        return 0

    return round(sum(changes) / len(changes), 2)


def analyze_stock(symbol):
    symbol = symbol.upper().strip()

    try:
        quote = get_json(
            "quote",
            {
                "symbol": symbol
            }
        )

        history = get_json(
            "time_series",
            {
                "symbol": symbol,
                "interval": "1day",
                "outputsize": 60
            }
        )

        values = history.get("values", [])

        if len(values) < 50:
            return {
                "error": "Not enough historical data."
            }

        # Twelve Data returns newest data first.
        # Reverse it so prices run oldest -> newest.
        prices = [
            float(item["close"])
            for item in reversed(values)
        ]

        price = float(quote["close"])
        daily_change = float(quote["percent_change"])

        ma20 = sum(prices[-20:]) / 20
        ma50 = sum(prices[-50:]) / 50

        rsi = calculate_rsi(prices)

        momentum_5d = (
            (prices[-1] - prices[-6]) / prices[-6]
        ) * 100

        volatility = calculate_volatility(prices[-21:])

        score = 50
        reasons = []

        # Trend
        if price > ma20:
            score += 10
            reasons.append("Price is above the 20-day average.")
        else:
            score -= 10
            reasons.append("Price is below the 20-day average.")

        if ma20 > ma50:
            score += 15
            reasons.append(
                "The 20-day average is above the 50-day average."
            )
        else:
            score -= 15
            reasons.append(
                "The 20-day average is below the 50-day average."
            )

        # RSI
        if rsi is not None:
            if 50 <= rsi < 70:
                score += 10
                reasons.append("RSI shows positive momentum.")
            elif rsi >= 70:
                score -= 5
                reasons.append("RSI may indicate overbought conditions.")
            elif rsi < 30:
                score += 5
                reasons.append("RSI may indicate oversold conditions.")
            else:
                score -= 5
                reasons.append("RSI shows weaker momentum.")

        # 5-day momentum
        if momentum_5d > 2:
            score += 10
            reasons.append("Five-day momentum is positive.")
        elif momentum_5d < -2:
            score -= 10
            reasons.append("Five-day momentum is negative.")

        score = max(0, min(100, round(score)))

        if score >= 70:
            signal = "BUY 📈"
        elif score <= 30:
            signal = "SELL 📉"
        else:
            signal = "HOLD"

        if volatility >= 3:
            risk = "High"
        elif volatility >= 1.5:
            risk = "Medium"
        else:
            risk = "Low"

        return {
            "symbol": symbol,
            "company": quote.get("name", symbol),
            "price": round(price, 2),
            "change": round(daily_change, 2),

            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "rsi": rsi,
            "momentum": round(momentum_5d, 2),
            "volatility": volatility,

            "signal": signal,
            "score": score,
            "confidence": score,
            "risk": risk,

            "reason": " ".join(reasons),
            "mode": "Live Market Data + Technical Analysis"
        }

    except requests.RequestException as error:
        return {
            "error": f"Market connection failed: {error}"
        }

    except (ValueError, KeyError, TypeError) as error:
        return {
            "error": f"Market data error: {error}"
        }