const service = document.getElementById("service");
const date = document.getElementById("date");
const time = document.getElementById("time");
const form = document.getElementById("bookingForm");
const message = document.getElementById("bookingMessage");
const sendCodeButton = document.getElementById("sendCodeButton");
const confirmButton = document.getElementById("confirmButton");
const backButton = document.getElementById("backButton");
const bookingDetails = document.getElementById("bookingDetails");
const otpStep = document.getElementById("otpStep");
const code = document.getElementById("code");
const otpEmail = document.getElementById("otpEmail");

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

function bookingPayload() {
    return {
        name: document.getElementById("name").value,
        email: document.getElementById("email").value,
        phone: document.getElementById("phone").value,
        service: service.value,
        start_at: time.value,
        website: document.getElementById("website").value
    };
}

async function loadServices() {
    const response = await fetch("/api/services");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load services.");
    service.innerHTML = data.services.map(item => `<option value="${item.name}">${item.name.replace(/\b\w/g, c => c.toUpperCase())} · ${item.duration_minutes} min</option>`).join("");
}

async function loadSlots() {
    time.disabled = true;
    sendCodeButton.disabled = true;
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
    sendCodeButton.disabled = !time.value;
});

sendCodeButton.addEventListener("click", async () => {
    if (!time.value || sendCodeButton.disabled) return;

    sendCodeButton.disabled = true;
    setMessage("Sending verification code…");

    try {
        const response = await fetch("/api/bookings/request-code", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bookingPayload())
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to send the verification code.");

        otpEmail.textContent = document.getElementById("email").value;
        bookingDetails.hidden = true;
        otpStep.hidden = false;
        code.value = "";
        code.focus();
        setMessage("Verification code sent. Check your email.");
    } catch (error) {
        setMessage(error.message, true);
        sendCodeButton.disabled = false;
    }
});

backButton.addEventListener("click", () => {
    otpStep.hidden = true;
    bookingDetails.hidden = false;
    setMessage("You can change your booking details and request a new code.");
    sendCodeButton.disabled = !time.value;
});

form.addEventListener("submit", async event => {
    event.preventDefault();
    if (otpStep.hidden || confirmButton.disabled) return;

    const enteredCode = code.value.trim();
    if (!/^\d{6}$/.test(enteredCode)) {
        setMessage("Enter the 6-digit verification code.", true);
        code.focus();
        return;
    }

    confirmButton.disabled = true;
    setMessage("Verifying code and confirming your appointment…");

    try {
        const response = await fetch("/api/bookings/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...bookingPayload(), code: enteredCode })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "The booking could not be confirmed.");

        const booking = data.booking;
        setMessage(`Confirmed: ${booking.service} at ${formatTime(booking.start_at)}. A confirmation email has been sent${data.confirmation_email_sent ? "." : ", but the email could not be sent."}`);
        form.reset();
        otpStep.hidden = true;
        bookingDetails.hidden = false;
        time.disabled = true;
        time.innerHTML = "<option value=\"\">Choose a date first</option>";
        sendCodeButton.disabled = true;
    } catch (error) {
        setMessage(error.message, true);
        if (!error.message.includes("attempts remaining") && !error.message.includes("Too many incorrect")) {
            confirmButton.disabled = false;
        }
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
