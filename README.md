# AI Booking System

Fictional AI customer-support and appointment-booking demo.

## Features

- Groq-powered customer support with live availability and booking tool use.
- Server-side SQLite booking store with overlap protection.
- Google Calendar sync is optional and disabled unless configured.
- Per-IP request limits, per-email booking limits, per-network booking limits, duplicate protection and honeypot protection.
- Server-side validation of service, date, time, business hours and booking horizon.
- Secure session cookie and security headers.
- Protected owner calendar view at `/calendar.html`.
- Calendar export at `/api/calendar.ics`.

## Recommended Groq model

Set `GROQ_MODEL=openai/gpt-oss-120b`. It supports tool use and structured outputs and is the strongest fit here. GPT-OSS 20B is a cheaper/faster alternative for a lightweight demo.

## Environment

```env
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
ADMIN_TOKEN=choose-a-long-random-value
ALLOWED_ORIGINS=https://your-demo-domain.example

# Optional Google Calendar sync
GOOGLE_CALENDAR_ID=your_calendar_id
GOOGLE_SERVICE_ACCOUNT_JSON={...service-account-json...}
```

For Google Calendar sync, create a Google Cloud project, enable the Calendar API, create a service account, and share the business calendar with the service account email with permission to manage events. Keep the service-account JSON secret out of Git. Google documents the Calendar API and authentication setup in its official developer documentation.

If Google Calendar is not configured, the demo still works using its local calendar database and owner calendar page.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

This repository contains fictional business data and is not a production booking service. A real deployment should add customer email verification, bot challenges/CAPTCHA where appropriate, persistent production storage, audit logging, staff authentication, backups, cancellation/rescheduling workflows, and a proper OAuth-based Google Calendar connection when customer accounts need to authorize access.
