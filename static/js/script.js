const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");

sendButton.addEventListener("click", sendMessage);

function sendMessage() {
    const message = userInput.value;

    if (message.trim() === "") {
        return;
    }

    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.textContent = message;

chatBox.appendChild(userMessage);

userInput.value = "";

setTimeout(function () {
    const aiMessage = document.createElement("div");
    aiMessage.className = "message ai-message";
    aiMessage.textContent = "Hi! I am Project Nova. Soon I will be connected to real AI.";

    chatBox.appendChild(aiMessage);
}, 500);
}