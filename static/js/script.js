const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.querySelector(".new-chat-btn");

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

    const time = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.innerHTML = `
        ${message}
        <br><small>${time}</small>
    `;

    chatBox.appendChild(userMessage);
    saveChat();
    chatBox.scrollTop = chatBox.scrollHeight;

    userInput.value = "";
setTimeout(() => {
    userInput.focus();
}, 0);
 const thinkingMessage = document.createElement("div");
    thinkingMessage.className = "message ai-message";
    thinkingMessage.innerHTML = `
        Nova is thinking...
        <br><small>${time}</small>
    `;

    chatBox.appendChild(thinkingMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
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

        thinkingMessage.innerHTML = `
            ${data.reply}
            <br><small>${time}</small>
        `;

        saveChat();
        chatBox.scrollTop = chatBox.scrollHeight;

    } catch (error) {
        thinkingMessage.innerHTML = `
            Nova is not connected to AI credits yet. We can keep building the website for now.
            <br><small>${time}</small>
        `;

        saveChat();
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

newChatButton.addEventListener("click", function () {
    chatBox.innerHTML = "";

    const welcomeMessage = document.createElement("div");
    welcomeMessage.className = "message ai-message";
    welcomeMessage.textContent = "Hello! I'm Project Nova. How can I help you today?";

    chatBox.appendChild(welcomeMessage);
    saveChat();

    setTimeout(() => {
        userInput.focus();
    }, 0);
});

function saveChat() {
    localStorage.setItem("projectNovaChat", chatBox.innerHTML);
}

function loadChat() {
    const savedChat = localStorage.getItem("projectNovaChat");

    if (savedChat) {
        chatBox.innerHTML = savedChat;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

loadChat();
userInput.focus();

const conversationList = document.getElementById("conversation-list");

let conversations = JSON.parse(
    localStorage.getItem("projectNovaConversations")
) || [];

function saveConversations() {
    localStorage.setItem(
        "projectNovaConversations",
        JSON.stringify(conversations)
    );
}

function renderConversations() {
    conversationList.innerHTML = "";

    conversations.forEach(function (conversation, index) {
        const conversationButton = document.createElement("button");

        conversationButton.className = "conversation-button";
        conversationButton.textContent = conversation.title;

        conversationButton.addEventListener("click", function () {
            chatBox.innerHTML = conversation.messages;
            localStorage.setItem("projectNovaChat", conversation.messages);
            chatBox.scrollTop = chatBox.scrollHeight;
            userInput.focus();
        });

        conversationList.appendChild(conversationButton);
    });
}

renderConversations();