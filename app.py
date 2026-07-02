from flask import Flask, render_template, request, jsonify
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data["message"]
    return jsonify({
        "reply": f"You said: {user_message}"
    })

if __name__ == "__main__":
    app.run(debug=True)
