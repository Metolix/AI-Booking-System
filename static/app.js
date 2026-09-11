const messages = document.getElementById("messages");
const input = document.getElementById("message");
const send = document.getElementById("send");
const suggestions = document.querySelectorAll("[data-message]");

let history = [];

function getConfigValue(config, path) {
    return path.split(".").reduce((value, key) => value?.[key], config);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[character]));
}

function escapeAttribute(value) {
    return String(value).replace(/[^a-zA-Z0-9/_-]/g, "");
}

async function loadSiteConfig() {
    try {
        const response = await fetch("/api/site-config");
        if (!response.ok) return;
        const config = await response.json();

        document.querySelectorAll("[data-config]").forEach(element => {
            const value = getConfigValue(config, element.dataset.config);
            if (value !== undefined && value !== null) element.textContent = value;
        });

        document.querySelectorAll("[data-config-href]").forEach(element => {
            const value = getConfigValue(config, element.dataset.configHref);
            if (value) element.href = value;
        });

        const businessName = getConfigValue(config, "business.name") || "Business";
        const assistantName = getConfigValue(config, "business.assistant_name") || `${businessName} Assistant`;
        const initial = getConfigValue(config, "business.initial_message");
        const bookingPath = getConfigValue(config, "booking.path") || "/book";

        document.title = `${businessName} — AI Support`;
        document.querySelectorAll(".business-name").forEach(element => { element.textContent = assistantName; });

        const welcome = document.getElementById("welcomeMessage");
        if (welcome && initial) {
            welcome.innerHTML = `${escapeHtml(initial)} When you're ready, you can <a href="${escapeAttribute(bookingPath)}">book an appointment</a>.`;
        }
    } catch {
    }
}

function addMessage(text, role) {
    const element = document.createElement("div");
    element.className = `message ${role}`;
    if (role === "assistant") {
        element.innerHTML = DOMPurify.sanitize(marked.parse(text));
    } else {
        element.textContent = text;
    }
    messages.appendChild(element);
    messages.scrollTop = messages.scrollHeight;
}

function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text || send.disabled) return;

    addMessage(text, "user");
    input.value = "";
    resizeInput();
    send.disabled = true;
    input.disabled = true;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, history: history.slice(-10) })
        });
        const data = await response.json();
        if (!response.ok) {
            if (response.status === 429) throw new Error("You're sending messages a little too quickly. Please wait a moment and try again.");
            throw new Error(data.detail || "Something went wrong.");
        }

        addMessage(data.response, "assistant");
        history.push({ role: "user", content: text });
        history.push({ role: "assistant", content: data.response });
    } catch (error) {
        addMessage(error.message || "Sorry, I'm unable to respond right now. Please contact the business directly.", "assistant");
    } finally {
        send.disabled = false;
        input.disabled = false;
        input.focus();
    }
}

suggestions.forEach(button => {
    button.addEventListener("click", () => {
        input.value = button.dataset.message;
        resizeInput();
        input.focus();
        sendMessage();
    });
});

send.addEventListener("click", sendMessage);
input.addEventListener("input", resizeInput);
input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

loadSiteConfig();
resizeInput();
