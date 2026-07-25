import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TWELVE_DATA_API_KEY")


def analyze_stock(symbol):

    symbol = symbol.upper().strip()

    url = (
        f"https://api.twelvedata.com/quote"
        f"?symbol={symbol}"
        f"&apikey={API_KEY}"
    )

    response = requests.get(url)

    data = response.json()

    if "code" in data:
        return {
            "error": data.get("message", "Unknown error.")
        }

    price = float(data["close"])
    change = float(data["percent_change"])

    if change > 2:
        signal = "BUY 📈"
        confidence = 90
        risk = "Low"
        reason = "Strong positive momentum today."
    elif change < -2:
        signal = "SELL 📉"
        confidence = 90
        risk = "High"
        reason = "The stock is under heavy selling pressure."
    else:
        signal = "HOLD"
        confidence = 75
        risk = "Medium"
        reason = "Price movement is relatively neutral."

    return {
        "symbol": symbol,
        "company": data["name"],
        "price": round(price, 2),
        "change": round(change, 2),
        "signal": signal,
        "confidence": confidence,
        "risk": risk,
        "reason": reason,
        "mode": "Live Market Data"
    }