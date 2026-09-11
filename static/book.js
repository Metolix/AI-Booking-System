const service = document.getElementById("service");
const date = document.getElementById("date");
const time = document.getElementById("time");
const form = document.getElementById("bookingForm");
const message = document.getElementById("bookingMessage");
const button = document.getElementById("bookButton");

function localDateString() {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function formatTime(value) {
    return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function setMessage(text, error = false) {
    message.textContent = text;
    message.style.color = error ? "#b91c1c" : "#555";
}

async function loadServices() {
    const response = await fetch("/api/services");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load services.");
    service.innerHTML = data.services.map(item => `<option value="${item.name}">${item.name.replace(/\b\w/g, c => c.toUpperCase())} · ${item.duration_minutes} min</option>`).join("");
}

async function loadSlots() {
    time.disabled = true;
    button.disabled = true;
    time.innerHTML = "<option value=\"\">Checking availability…</option>";
    setMessage("");

    if (!service.value || !date.value) return;

    try {
        const response = await fetch("/api/availability", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ service: service.value, date: date.value })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to check availability.");

        if (!data.slots.length) {
            time.innerHTML = "<option value=\"\">No times available</option>";
            setMessage("There are no available times for this service on that date.");
            return;
        }

        time.innerHTML = `<option value="">Choose a time</option>${data.slots.map(slot => `<option value="${slot}">${formatTime(slot)}</option>`).join("")}`;
        time.disabled = false;
        setMessage(`${data.slots.length} available time${data.slots.length === 1 ? "" : "s"}.`);
    } catch (error) {
        time.innerHTML = "<option value=\"\">Unable to load times</option>";
        setMessage(error.message, true);
    }
}

service.addEventListener("change", loadSlots);
date.addEventListener("change", loadSlots);
time.addEventListener("change", () => {
    button.disabled = !time.value;
});

form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!time.value || button.disabled) return;

    button.disabled = true;
    setMessage("Booking your appointment…");

    try {
        const response = await fetch("/api/bookings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: document.getElementById("name").value,
                email: document.getElementById("email").value,
                phone: document.getElementById("phone").value,
                service: service.value,
                start_at: time.value,
                website: document.getElementById("website").value
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "The booking could not be completed.");

        const booking = data.booking;
        setMessage(`Confirmed: ${booking.service} at ${formatTime(booking.start_at)}. A confirmation email has been sent${data.confirmation_email_sent ? "." : ", but the email could not be sent."}`);
        form.reset();
        time.disabled = true;
        time.innerHTML = "<option value=\"\">Choose a date first</option>";
    } catch (error) {
        setMessage(error.message, true);
        await loadSlots();
    }
});

(async function init() {
    const today = localDateString();
    date.min = today;
    try {
        await loadServices();
        date.value = today;
        await loadSlots();
    } catch (error) {
        setMessage(error.message, true);
    }
})();
