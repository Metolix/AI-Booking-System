const messages = document.getElementById("messages");
const input = document.getElementById("message");
const send = document.getElementById("send");

let history = [];

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

async function sendMessage() {

    const text = input.value.trim();

    if (!text || send.disabled) {
        return;
    }

    addMessage(text, "user");

    history.push({
        role: "user",
        content: text
    });

    input.value = "";

    send.disabled = true;
    input.disabled = true;

    try {

        const response = await fetch("/api/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: text,
                history: history.slice(-10)
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Something went wrong."
            );
        }

        addMessage(data.response, "assistant");

        history.push({
            role: "assistant",
            content: data.response
        });

    } catch (error) {

        addMessage(
            "Sorry, I'm unable to respond right now. Please contact the business directly.",
            "assistant"
        );

    } finally {

        send.disabled = false;
        input.disabled = false;

        input.focus();
    }
}

send.addEventListener("click", sendMessage);

input.addEventListener("keydown", event => {

    if (
        event.key === "Enter" &&
        !event.shiftKey
    ) {
        event.preventDefault();
        sendMessage();
    }

});