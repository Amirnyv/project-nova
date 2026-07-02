const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");

sendButton.addEventListener("click", sendMessage);

userInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});

async function sendMessage() {
    const message = userInput.value;

    if (message.trim() === "") {
        return;
    }

    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.textContent = message;

    chatBox.appendChild(userMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    userInput.value = "";

const thinkingMessage = document.createElement("div");
thinkingMessage.className = "message ai-message";
thinkingMessage.textContent = "Nova is thinking...";

chatBox.appendChild(thinkingMessage);
chatBox.scrollTop = chatBox.scrollHeight;

const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message: message
        })
    });

   const data = await response.json();

thinkingMessage.textContent = data.reply;
    chatBox.scrollTop = chatBox.scrollHeight;
}