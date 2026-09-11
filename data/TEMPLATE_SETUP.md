# Client Setup

This template is designed so a new client can be configured without changing the frontend code.

## 1. Business information

Edit `data/company_info.txt` with the client's real business information. The AI uses this file as its business knowledge source.

## 2. Site configuration

Edit `data/site_config.json` for the website and booking experience.

Common fields to change:

- `business.name` — business name shown across the site
- `business.short_name` — short brand name
- `business.type` — business category
- `business.tagline` — short brand message
- `business.assistant_name` — AI assistant name
- `business.initial_message` — opening chat message
- `business.demo_label` — remove or change `DEMO` for a production client
- `business.demo_description` — top banner description
- `booking.title` — booking page heading
- `booking.description` — booking page description
- `booking.calendar_label` — calendar status text
- `booking.max_days_ahead` — booking window
- `booking.timezone` — IANA timezone, such as `America/Toronto` or `Asia/Dubai`
- `branding.logo_text` — temporary text logo
- `contact.*` — phone, email, website and social handle
- `footer.*` — footer copy

## 3. Services

Edit `data/services.json` to add, remove or change bookable services and their durations.

The service names and durations are used by the availability and booking system. Keep the durations in minutes.

## 4. Calendar and email

Set the client's production environment variables for Google Calendar, email delivery, Groq and OTP security.

Never put API keys, passwords, service-account JSON or other secrets in `data/site_config.json` or `data/company_info.txt`.

## 5. Client handoff

For each client, update `company_info.txt`, `site_config.json`, and `services.json`, then configure the environment variables and connect the client's Google Calendar.
