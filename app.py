from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
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