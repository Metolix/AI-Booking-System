# AI Booking System

Fictional AI customer-support and appointment-booking demo.

## How bookings work

Bookings are handled only through the AI chat.

Before confirming an appointment, the AI:

- checks the requested date against the business's opening hours;
- checks Google Calendar for existing events that overlap the requested appointment;
- requires the customer's name, email, phone number, service and appointment time;
- creates the appointment directly in Google Calendar only after validation succeeds.

There is no separate booking database, direct booking form, local owner calendar or calendar export.

## Google Calendar setup

Google Calendar is required for booking. Set:

```env
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
ALLOWED_ORIGINS=https://your-demo-domain.example
GOOGLE_CALENDAR_ID=your_calendar_id
GOOGLE_SERVICE_ACCOUNT_JSON={...service-account-json...}
```

Create a Google Cloud project, enable the Google Calendar API, create a service account, and share the business calendar with that service account with permission to manage events. Keep the service-account JSON out of Git.

If Google Calendar is not configured, the AI can still answer business questions but cannot check availability or create appointments.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

This repository uses fictional business data for demonstration purposes.
