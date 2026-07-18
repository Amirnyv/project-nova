const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.querySelector(".new-chat-btn");
const conversationList = document.getElementById("conversation-list");

let conversations =
    JSON.parse(localStorage.getItem("projectNovaConversations")) || [];

let activeConversationId =
    localStorage.getItem("projectNovaActiveConversationId") || null;

sendButton.addEventListener("click", sendMessage);

userInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});

newChatButton.addEventListener("click", startNewChat);

async function sendMessage() {
    const message = userInput.value.trim();

    if (message === "") {
        return;
    }

    const time = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.innerHTML = `
        ${escapeHtml(message)}
        <br><small>${time}</small>
    `;

    chatBox.appendChild(userMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    userInput.value = "";
    userInput.focus();

    ensureActiveConversation(message);
    saveCurrentConversation();

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

        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        const data = await response.json();

        thinkingMessage.innerHTML = `
            ${escapeHtml(data.reply)}
            <br><small>${time}</small>
        `;
    } catch (error) {
        thinkingMessage.innerHTML = `
            Nova is not connected to AI credits yet. We can keep building the website for now.
            <br><small>${time}</small>
        `;
    }

    saveCurrentConversation();
    chatBox.scrollTop = chatBox.scrollHeight;
}

function startNewChat() {
    saveCurrentConversation();

    activeConversationId = null;
    localStorage.removeItem("projectNovaActiveConversationId");

    chatBox.innerHTML = "";

    const welcomeMessage = document.createElement("div");
    welcomeMessage.className = "message ai-message";
    welcomeMessage.textContent =
        "Hello! I'm Project Nova. How can I help you today?";

    chatBox.appendChild(welcomeMessage);

    localStorage.setItem("projectNovaChat", chatBox.innerHTML);

    renderConversations();
    userInput.focus();
}

function ensureActiveConversation(firstMessage) {
    if (activeConversationId !== null) {
        return;
    }

    const conversation = {
        id: crypto.randomUUID(),
        title: createConversationTitle(firstMessage),
        messages: chatBox.innerHTML,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
    };

    conversations.unshift(conversation);
    activeConversationId = conversation.id;

    localStorage.setItem(
        "projectNovaActiveConversationId",
        activeConversationId
    );

    saveConversations();
    renderConversations();
}

function saveCurrentConversation() {
    localStorage.setItem("projectNovaChat", chatBox.innerHTML);

    if (activeConversationId === null) {
        return;
    }

    const conversation = conversations.find(function (item) {
        return item.id === activeConversationId;
    });

    if (!conversation) {
        return;
    }

    conversation.messages = chatBox.innerHTML;
    conversation.updatedAt = new Date().toISOString();

    saveConversations();
    renderConversations();
}

function loadConversation(conversationId) {
    const conversation = conversations.find(function (item) {
        return item.id === conversationId;
    });

    if (!conversation) {
        return;
    }

    activeConversationId = conversation.id;

    localStorage.setItem(
        "projectNovaActiveConversationId",
        activeConversationId
    );

    chatBox.innerHTML = conversation.messages;
    localStorage.setItem("projectNovaChat", conversation.messages);

    chatBox.scrollTop = chatBox.scrollHeight;
    renderConversations();
    userInput.focus();
}

function saveConversations() {
    localStorage.setItem(
        "projectNovaConversations",
        JSON.stringify(conversations)
    );
}

function renderConversations() {
    conversationList.innerHTML = "";

    conversations.forEach(function (conversation) {
        const conversationButton = document.createElement("button");

        conversationButton.className = "conversation-button";
        conversationButton.textContent = conversation.title;

        if (conversation.id === activeConversationId) {
            conversationButton.classList.add("active");
        }

        conversationButton.addEventListener("click", function () {
            loadConversation(conversation.id);
        });

        conversationList.appendChild(conversationButton);
    });
}

function createConversationTitle(message) {
    const cleanedMessage = message.replace(/\s+/g, " ").trim();

    if (cleanedMessage.length <= 28) {
        return cleanedMessage;
    }

    return `${cleanedMessage.slice(0, 28)}...`;
}

function escapeHtml(text) {
    const element = document.createElement("div");
    element.textContent = text;
    return element.innerHTML;
}

function loadSavedState() {
    renderConversations();

    if (activeConversationId !== null) {
        const activeConversation = conversations.find(function (item) {
            return item.id === activeConversationId;
        });

        if (activeConversation) {
            chatBox.innerHTML = activeConversation.messages;
            chatBox.scrollTop = chatBox.scrollHeight;
            return;
        }
    }

    const savedChat = localStorage.getItem("projectNovaChat");

    if (savedChat) {
        chatBox.innerHTML = savedChat;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

loadSavedState();
userInput.focus();