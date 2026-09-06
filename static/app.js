const messages = document.getElementById("messages");
const input = document.getElementById("message");
const send = document.getElementById("send");
const bookingForm = document.getElementById("bookingForm");
const bookingDate = document.getElementById("bookingDate");
const bookingService = document.getElementById("bookingService");
const bookingTime = document.getElementById("bookingTime");
const bookingMessage = document.getElementById("bookingMessage");
const bookButton = document.getElementById("bookButton");
const calendarStatus = document.getElementById("calendarStatus");

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
    if (!text || send.disabled) return;
    addMessage(text, "user");
    input.value = "";
    send.disabled = true;
    input.disabled = true;
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, history: history.slice(-10) })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Something went wrong.");
        addMessage(data.response, "assistant");
        history.push({ role: "user", content: text });
        history.push({ role: "assistant", content: data.response });
    } catch (error) {
        addMessage("Sorry, I'm unable to respond right now. Please contact the business directly.", "assistant");
    } finally {
        send.disabled = false;
        input.disabled = false;
        input.focus();
    }
}

async function loadSlots() {
    const date = bookingDate.value;
    const service = bookingService.value;
    if (!date) {
        bookingTime.innerHTML = "<option>Select a date first</option>";
        bookingTime.disabled = true;
        return;
    }
    bookingTime.disabled = true;
    bookingTime.innerHTML = "<option>Checking availability…</option>";
    bookingMessage.textContent = "";
    try {
        const response = await fetch(`/api/availability?date=${encodeURIComponent(date)}&service=${encodeURIComponent(service)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to check availability.");
        calendarStatus.textContent = data.calendar_sync ? "Google Calendar" : "Demo calendar";
        bookingTime.innerHTML = "";
        if (!data.slots.length) {
            bookingTime.innerHTML = "<option>No times available</option>";
            return;
        }
        data.slots.forEach(slot => {
            const option = document.createElement("option");
            const dateObject = new Date(slot);
            option.value = slot;
            option.textContent = dateObject.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
            bookingTime.appendChild(option);
        });
        bookingTime.disabled = false;
    } catch (error) {
        bookingTime.innerHTML = "<option>Unable to load times</option>";
        bookingMessage.textContent = error.message;
    }
}

async function submitBooking(event) {
    event.preventDefault();
    bookButton.disabled = true;
    bookingMessage.textContent = "Confirming appointment…";
    try {
        const response = await fetch("/api/bookings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: document.getElementById("bookingName").value.trim(),
                email: document.getElementById("bookingEmail").value.trim(),
                phone: document.getElementById("bookingPhone").value.trim(),
                service: bookingService.value,
                start_at: bookingTime.value,
                website: document.getElementById("website").value
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to create the appointment.");
        const when = new Date(data.start_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
        bookingMessage.textContent = `Confirmed — ${data.service} on ${when}.`;
        bookingForm.reset();
        bookingTime.innerHTML = "<option>Select a date first</option>";
        bookingTime.disabled = true;
        addMessage(`Your appointment is confirmed for **${when}**. Booking ID: \`${data.id.slice(0, 8)}\`.`, "assistant");
    } catch (error) {
        bookingMessage.textContent = error.message;
        await loadSlots();
    } finally {
        bookButton.disabled = false;
    }
}

send.addEventListener("click", sendMessage);
input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});
bookingDate.addEventListener("change", loadSlots);
bookingService.addEventListener("change", loadSlots);
bookingForm.addEventListener("submit", submitBooking);

const today = new Date();
const minDate = today.toISOString().slice(0, 10);
const max = new Date(today);
max.setDate(max.getDate() + 60);
bookingDate.min = minDate;
bookingDate.max = max.toISOString().slice(0, 10);
