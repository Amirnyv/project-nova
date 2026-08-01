const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.querySelector(".new-chat-btn");
const conversationList = document.getElementById("conversation-list");

const navButtons = document.querySelectorAll(".nav-button");
const pages = document.querySelectorAll(".page");
const marketSymbol = document.getElementById("market-symbol");
const marketSearchButton = document.getElementById("market-search-button");
const marketResults = document.getElementById("market-results");
const portfolioValue = document.getElementById("portfolio-value");
const portfolioCash = document.getElementById("portfolio-cash");
const portfolioProfit = document.getElementById("portfolio-profit");
const portfolioPositions = document.getElementById("portfolio-positions");
const portfolioHistory = document.getElementById("portfolio-history");

let conversations =
    JSON.parse(localStorage.getItem("projectNovaConversations")) || [];
    conversations = conversations.map(function (conversation) {
    return {

        ...conversation,

        topic:
        conversation.topic ||
        detectTopic(
        conversation.title || ""
        ),

        goal:
        conversation.goal ||
        detectGoal(
        conversation.title || ""
        ),
        context:
conversation.context ||
"Starting Conversation",

        messageCount:
        conversation.messageCount || 0

};
});

localStorage.setItem(
    "projectNovaConversations",
    JSON.stringify(conversations)
);

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
    const conversationHistory = getConversationHistory();

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
    message: message,
    history: conversationHistory
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

if (data.stock_data) {
    createStockChart(
        thinkingMessage,
        data.stock_data
    );
}
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
        topic: detectTopic(firstMessage),
        goal: detectGoal(firstMessage),
        context: "Starting Conversation",
        messageCount: 1,
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
const lastUserMessage = chatBox.querySelector(
    ".user-message:last-of-type"
);

if (lastUserMessage) {
    conversation.context = detectContext(
        lastUserMessage.textContent
    );
}

const totalMessages =
chatBox.querySelectorAll(".user-message").length;

conversation.messageCount = totalMessages;

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
        const conversationRow = document.createElement("div");
        conversationRow.className = "conversation-row";

        const conversationButton = document.createElement("button");
        conversationButton.className = "conversation-button";

        conversationButton.innerHTML = `

${conversation.title}

<br>

<small>
${conversation.topic}
</small>

<br>

<small>
${conversation.goal}
</small>

<br>

<small>
${conversation.context}
</small>

<br>

<small>
${conversation.messageCount} messages
</small>

<br>

<small>
${formatLastActive(conversation.updatedAt)}
</small>

`;

        if (conversation.id === activeConversationId) {
            conversationButton.classList.add("active");
        }

        conversationButton.addEventListener("click", function () {
            loadConversation(conversation.id);
        });

        const deleteButton = document.createElement("button");
        deleteButton.className = "delete-conversation-button";
        deleteButton.textContent = "×";
        deleteButton.setAttribute("aria-label", "Delete conversation");

        deleteButton.addEventListener("click", function (event) {
            event.stopPropagation();
            deleteConversation(conversation.id);
        });

        conversationRow.appendChild(conversationButton);
        conversationRow.appendChild(deleteButton);
        conversationList.appendChild(conversationRow);
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

function getConversationHistory() {
    const messageElements = chatBox.querySelectorAll(".message");

    return Array.from(messageElements)
        .map(function (messageElement) {
            const messageCopy = messageElement.cloneNode(true);

            messageCopy.querySelectorAll("small").forEach(function (small) {
                small.remove();
            });

            const content = messageCopy.textContent.trim();

            if (
                content === "" ||
                content === "Nova is thinking..." ||
                content.startsWith("Nova is not connected")
            ) {
                return null;
            }

            const role = messageElement.classList.contains("user-message")
                ? "user"
                : "assistant";

            return {
                role: role,
                content: content
            };
        })
        .filter(function (message) {
            return message !== null;
        });
}

function detectTopic(message) {

    const text = message.toLowerCase();

    if (
        text.includes("python") ||
        text.includes("javascript") ||
        text.includes("coding") ||
        text.includes("programming")
    ) {
        return "Programming";
    }

    if (
        text.includes("stock") ||
        text.includes("tesla") ||
        text.includes("bitcoin") ||
        text.includes("crypto")
    ) {
        return "Finance";
    }

    if (
        text.includes("homework") ||
        text.includes("school") ||
        text.includes("essay")
    ) {
        return "Education";
    }

    if (
        text.includes("travel") ||
        text.includes("vacation") ||
        text.includes("hotel")
    ) {
        return "Travel";
    }

    return "General";
}

function detectGoal(message) {

    const text = message.toLowerCase();

    if (text.includes("nova") || text.includes("project")) {
        return "Building Project Nova";
    }

    if (text.includes("flask")) {
        return "Building Project Nova";
    }

    if (text.includes("python")) {
        return "Learning Python";
    }

    if (text.includes("stock") || text.includes("tesla")) {
        return "Learning Stocks";
    }

    if (text.includes("bitcoin") || text.includes("crypto")) {
        return "Learning Crypto";
    }

    if (text.includes("essay")) {
        return "Writing Essays";
    }

    if (text.includes("travel")) {
        return "Planning A Trip";
    }

    return "General Learning";
}

function detectContext(message) {

    const text = message.toLowerCase();

    if (text.includes("flask")) {
        return "Building Flask Backend";
    }

    if (text.includes("python")) {
        return "Learning Python";
    }

    if (text.includes("memory")) {
        return "Building Memory System";
    }

    if (text.includes("api")) {
        return "Connecting OpenAI API";
    }

    if (text.includes("stock")) {
        return "Building Trading System";
    }

    if (text.includes("debug")) {
        return "Debugging";
    }

    return "General Discussion";
}

function formatLastActive(dateString) {

    if (!dateString) {
        return "Just now";
    }

    const now = new Date();
    const date = new Date(dateString);

    const difference =
    Math.floor((now - date) / 60000);

    if (difference < 1) {
        return "Just now";
    }

    if (difference < 60) {
        return `${difference} minutes ago`;
    }

    if (difference < 1440) {
        return `${Math.floor(difference / 60)} hours ago`;
    }

    return `${Math.floor(difference / 1440)} days ago`;
}

function deleteConversation(conversationId) {
    conversations = conversations.filter(function (conversation) {
        return conversation.id !== conversationId;
    });

    if (activeConversationId === conversationId) {
        activeConversationId = null;
        localStorage.removeItem("projectNovaActiveConversationId");

        chatBox.innerHTML = `
            <div class="message ai-message">
                Hello! I'm Project Nova. How can I help you today?
            </div>
        `;

        localStorage.setItem("projectNovaChat", chatBox.innerHTML);
    }

    saveConversations();
    renderConversations();
    userInput.focus();
}

loadSavedState();
userInput.focus();

function createStockChart(messageElement, stockData) {
    const chartContainer = document.createElement("div");
    chartContainer.className = "stock-chart-container";

    const canvas = document.createElement("canvas");

    chartContainer.appendChild(canvas);
    messageElement.appendChild(chartContainer);

    new Chart(canvas, {
        type: "line",

        data: {
            labels: stockData.dates,

            datasets: [
    {
        label: `${stockData.symbol} Price`,
        data: stockData.prices,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2
    },
    {
        label: "20-Day MA",
        data: stockData.ma20,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2
    },
    {
        label: "50-Day MA",
        data: stockData.ma50,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2
    }
]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            interaction: {
                intersect: false,
                mode: "index"
            },

            scales: {
                x: {
                    ticks: {
                        maxTicksLimit: 8
                    }
                }
            }
        }
    });
}


function switchPage(pageName) {
    pages.forEach(function (page) {
        page.classList.remove("active-page");
    });

    navButtons.forEach(function (button) {
        button.classList.remove("active");
    });

    const selectedPage = document.getElementById(
        `${pageName}-page`
    );

    if (selectedPage) {
        selectedPage.classList.add("active-page");
    }

    const selectedButton = document.querySelector(
        `.nav-button[data-page="${pageName}"]`
    );

    if (selectedButton) {
        selectedButton.classList.add("active");
    }

if (pageName === "portfolio") {
    loadPortfolioDashboard();
}

if (pageName === "projects") {
    loadProjects();
}

if (pageName === "chat") {
    userInput.focus();
}

}
navButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        const pageName = button.dataset.page;
        switchPage(pageName);
    });
});

async function analyzeMarketSymbol() {
    const symbol = marketSymbol.value.trim().toUpperCase();

    if (symbol === "") {
        marketResults.textContent = "Enter a ticker symbol first.";
        return;
    }

    marketResults.textContent = "Nova is analyzing...";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: `Analyze ${symbol}`,
                history: []
            })
        });

        if (!response.ok) {
            throw new Error(
                `Request failed with status ${response.status}`
            );
        }

        const data = await response.json();

        marketResults.innerHTML = "";

        const analysisText = document.createElement("div");
        analysisText.textContent =
            data.reply || "No analysis returned.";

        marketResults.appendChild(analysisText);

        if (data.stock_data) {
            createStockChart(
                marketResults,
                data.stock_data
            );
        }

    } catch (error) {
        marketResults.textContent =
            "Nova could not analyze this stock.";
    }
}


marketSearchButton.addEventListener(
    "click",
    analyzeMarketSymbol
);


marketSymbol.addEventListener(
    "keydown",
    function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            analyzeMarketSymbol();
        }
    }
);

async function loadPortfolioDashboard() {
    portfolioPositions.textContent = "Loading portfolio...";
    portfolioHistory.textContent = "Loading trade history...";

    try {
        const portfolioResponse = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: "portfolio",
                history: []
            })
        });

        if (!portfolioResponse.ok) {
            throw new Error("Portfolio request failed.");
        }

        const portfolioData = await portfolioResponse.json();
        const portfolioText = portfolioData.reply || "";

        const cashMatch = portfolioText.match(
            /Cash:\s*\$([0-9,.]+)/
        );

        const valueMatch = portfolioText.match(
            /Portfolio Value:\s*\$([0-9,.]+)/
        );

        const profitMatch = portfolioText.match(
            /Total P\/L:\s*\$([+\-0-9,.]+)/
        );

        portfolioCash.textContent = cashMatch
            ? `$${cashMatch[1]}`
            : "$0.00";

        portfolioValue.textContent = valueMatch
            ? `$${valueMatch[1]}`
            : "$0.00";

        portfolioProfit.textContent = profitMatch
            ? `$${profitMatch[1]}`
            : "$0.00";

        portfolioPositions.textContent = portfolioText;

        const historyResponse = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: "trade history",
                history: []
            })
        });

        if (!historyResponse.ok) {
            throw new Error("Trade history request failed.");
        }

        const historyData = await historyResponse.json();

        portfolioHistory.textContent =
            historyData.reply || "No trades yet.";

    } catch (error) {
        portfolioPositions.textContent =
            "Could not load portfolio.";

        portfolioHistory.textContent =
            "Could not load trade history.";

        console.error(error);
    }
}

const projectsList =
    document.getElementById("projects-list");

const newProjectButton =
    document.getElementById("new-project-button");
    const projectModal =
    document.getElementById("project-modal");

const cancelProjectButton =
    document.getElementById("cancel-project");

const createProjectButton =
    document.getElementById("create-project");

const projectNameInput =
    document.getElementById("project-name");

const projectDescriptionInput =
    document.getElementById("project-description");


async function loadProjects() {

    projectsList.innerHTML =
        "<p>Loading projects...</p>";

    try {

        const response = await fetch(
            "/api/projects"
        );

        const data = await response.json();

        if (data.projects.length === 0) {

            projectsList.innerHTML =
                "<p>No projects yet.</p>";

            return;
        }

        projectsList.innerHTML = "";

        data.projects.forEach(function(project){

            const card =
                document.createElement("div");

            card.className = "dashboard-card";

            card.innerHTML = `
                <h3>${project.name}</h3>
                <p>${project.description}</p>
            `;

            projectsList.appendChild(card);

        });

    }
    catch(error){

        projectsList.innerHTML =
            "<p>Could not load projects.</p>";

        console.error(error);

    }

}

newProjectButton.addEventListener(
    "click",
    function () {

        projectModal.style.display = "flex";

        projectNameInput.value = "";
        projectDescriptionInput.value = "";

        projectNameInput.focus();

    }
);


cancelProjectButton.addEventListener(
    "click",
    function () {

        projectModal.style.display = "none";

    }
);


window.addEventListener(
    "click",
    function (event) {

        if (event.target === projectModal) {
            projectModal.style.display = "none";
        }

    }
);