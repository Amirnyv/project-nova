from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from agents.stock_agent import analyze_stock
import os

app = Flask(__name__)

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}

    user_message = data.get("message", "").strip()
    conversation_history = data.get("history", [])

    if not user_message:
        return jsonify({
            "error": "A message is required."
        }), 400

    messages = [
        {
            "role": "system",
            "content": (
    "You are Project Nova, an intelligent AI assistant. "
    "Remember the current conversation and remain consistent "
    "with its topic and context. "
    "If the conversation is about Python, continue helping "
    "with Python unless the user changes subjects. "
    "If it is about stocks, continue discussing stocks. "
    "Give clear, helpful, and professional responses."
)
        }
    ]

    for item in conversation_history:
        role = item.get("role")
        content = item.get("content", "").strip()

        if role in ("user", "assistant") and content:
            messages.append({
                "role": role,
                "content": content
            })

    messages.append({
        "role": "system",
        "content": (
            f"The current conversation contains "
            f"{len(conversation_history)} previous messages. "
            f"Use the earlier discussion when answering if it "
            f"is relevant."
        )
    })

    messages.append({
        "role": "user",
        "content": user_message
    })

    stock_keywords = [
        "aapl",
        "tsla",
        "btc",
        "bitcoin",
        "stock",
        "stocks",
        "analyze"
    ]

    if any(word in user_message.lower() for word in stock_keywords):
        symbol = None

        if "aapl" in user_message.lower():
            symbol = "AAPL"
        elif "tsla" in user_message.lower():
            symbol = "TSLA"
        elif "btc" in user_message.lower() or "bitcoin" in user_message.lower():
            symbol = "BTC"

        if symbol:
            result = analyze_stock(symbol)

            if "error" in result:
                return jsonify({
                    "reply": f"Stock Agent Error: {result['error']}"
                })

            return jsonify({
                "reply": (
                    f"📈 {result['company']} ({result['symbol']})\n\n"
                    f"💲 Current Price: ${result['price']}\n"
                    f"📊 Daily Change: {result['change']}%\n\n"
                    f"📉 20-Day Average: ${result['ma20']}\n"
                    f"📉 50-Day Average: ${result['ma50']}\n"
                    f"⚡ RSI (14): {result['rsi']}\n"
                    f"🚀 5-Day Momentum: {result['momentum']}%\n"
                    f"⚠️ Volatility: {result['volatility']}%\n\n"
                    f"🧠 Nova Score: {result['score']}/100\n"
                    f"🎯 Signal: {result['signal']}\n"
                    f"⚠️ Risk: {result['risk']}\n\n"
                                        f"💡 Analysis:\n{result['reason']}\n\n"
                    f"🌐 {result['mode']}"
                ),
                "stock_data": {
                    "symbol": result["symbol"],
                    "dates": result["chart_dates"],
                    "prices": result["chart_prices"]
                }
            })

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    
    reply = response.choices[0].message.content

    return jsonify({
        "reply": reply
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)