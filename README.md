# AI Receptionist — WhatsApp AI Receptionist for Clinics

> **Current Project Status: CHUNK 12 (Calendar Integration & Appointment Synchronization Completed)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, resilient AI Receptionist Engine (Gemini Primary + Groq Fallback), per-clinic WhatsApp Account Management, Meta Webhook verification & HMAC security, customer message ingestion, outbound WhatsApp AI reply dispatching via Meta Graph API, automated structured Lead Extraction & Qualification, Human Handoff Escalation, Appointment Booking System, Clinic Staff Dashboard, Automated WhatsApp Reminders (24h & 2h), and Google Calendar / Microsoft Outlook Synchronization with AES-256 encrypted credential management.

---

## 1. What the Project Is

**AI Receptionist** is a production-oriented SaaS platform engineered for **dental and aesthetic clinics in Karachi, Pakistan**.

The product enables clinics to automate patient communication through WhatsApp, offering:
* AI-driven answers to clinic-approved FAQs
* Service and pricing explanations
* Clinic information (hours, location, practitioner details)
* Patient lead capture and automated structured qualification
* Explicit & AI-detected human handoff and staff escalation queue
* Staff reply transmission to WhatsApp with audit logs
* Appointment intake, confirmation, rescheduling, and status tracking
* Automated WhatsApp appointment reminder dispatch (24 hours & 2 hours before scheduled time)
* External Calendar Synchronization (Google Calendar & Microsoft Outlook / Office 365)
* Clinic staff dashboard, calendar settings, and appointment management interface

---

## 2. Complete WhatsApp AI, Appointment & Calendar Pipeline

```text
                         CUSTOMER
                            │
                            ▼
                     META WHATSAPP
                            │
                            ▼
                  HMAC WEBHOOK SECURITY
                            │
                            ▼
                    TENANT RESOLUTION
                            │
                            ▼
                  MESSAGE PERSISTENCE
                            │
                            ▼
                 CONVERSATION RESOLUTION
                            │
                ┌───────────┴───────────┐
                │                       │
          HUMAN ACTIVE?             AI ACTIVE?
                │                       │
               YES                     YES
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │ WAIT FOR     │        │ AI RECEPTIONIST│
        │ STAFF        │        └───────┬───────┘
        └──────┬───────┘                │
               │                ┌───────┴────────┐
               │                │                │
               │             NORMAL          APPOINTMENT
               │                │             REQUEST
               │                ▼                ▼
               │           AI RESPONSE    APPOINTMENT RECORD
               │                          (status=requested)
               │                                 │
               │                                 ▼
               │                         ┌───────────────┐
               │                         │ STAFF QUEUE   │
               │                         └───────┬───────┘
               │                                 │
               │                              CONFIRM
               │                                 │
               │                                 ▼
               │                    ┌───────────────────────────┐
               │                    │ • SCHEDULE 24H/2H REMINDER│
               │                    │ • QUEUE CALENDAR SYNC     │
               │                    └────────────┬──────────────┘
               │                                 │
               │                                 ▼
               │                    EXTERNAL CALENDAR SYNC
               │                    (Google Calendar / Outlook)
               │                                 │
               │                                 ▼
               │                    AUTOMATED WHATSAPP REMINDERS
               │                    (24h & 2h before visit)
               │                                 │
               └──────────────────────┬──────────┘
                                      ▼
                                PATIENT VISIT
                                      │
                                      ▼
                                  COMPLETED
```

---

## 3. Technology Stack

### Backend
* **Language:** Python 3.11+
* **Framework:** FastAPI (Lifespan context manager + Background Scheduler for Reminders & Calendar Sync)
* **AI Providers:** Google Gemini API (Primary) & Groq API (Fallback)
* **Calendar Integrations:** Google Calendar API (`google-api-python-client`) & Microsoft Graph API
* **Integrations:** Meta WhatsApp Cloud API (Graph API `v20.0`)
* **Security:** Argon2id (`argon2-cffi`), PyJWT, HMAC-SHA256, AES-256/Fernet token encryption (`cryptography`)
* **Validation & Settings:** Pydantic v2 & Pydantic Settings
* **Database ORM:** SQLAlchemy 2.0
* **Migrations:** Alembic
* **Driver:** psycopg2-binary
* **Testing:** Pytest & HTTPX (216 tests passing)
* **ASGI Server:** Uvicorn

### Frontend
* **Framework:** Next.js 14+ (App Router)
* **Language:** TypeScript (Strict Mode)
* **Styling:** Tailwind CSS + PostCSS
* **Pages:** Dashboard, Appointments, Calendar Settings (`/settings/calendar`)

---

## 4. API Endpoints (v1)

### Calendar Integration & Synchronization (CHUNK 12)
* `GET /api/v1/calendar/connections` — List clinic calendar connections (Staff/Admin/Owner)
* `GET /api/v1/calendar/{provider}/connect` — Generate OAuth authorization URL (Owner/Admin)
* `GET /api/v1/calendar/{provider}/callback` — Handle OAuth callback and securely store encrypted credentials
* `POST /api/v1/calendar/{provider}/disconnect` — Disconnect provider and securely delete tokens (Owner/Admin)
* `GET /api/v1/calendar/calendars` — List available calendars under connected account (Staff/Admin/Owner)
* `POST /api/v1/calendar/select` — Set active calendar for appointment syncing (Owner/Admin)
* `POST /api/v1/calendar/sync` — Trigger immediate manual calendar synchronization (Staff/Admin/Owner)

### Appointment & Reminder Management (CHUNK 9 & CHUNK 11)
* `GET /api/v1/appointments` — List appointments with pagination and filters (`status`, `lead_id`, `conversation_id`, `date`, `date_from`, `date_to`)
* `POST /api/v1/appointments` — Create appointment, queue calendar sync, and auto-schedule 24h/2h reminders (Staff/Admin/Owner)
* `GET /api/v1/appointments/{appointment_id}` — Get appointment details (Staff/Admin/Owner)
* `PATCH /api/v1/appointments/{appointment_id}` — Update appointment details / reschedule reminders / sync calendar (Staff/Admin/Owner)
* `GET /api/v1/appointments/{appointment_id}/reminders` — Get reminder delivery logs and statuses (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/confirm` — Confirm appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/cancel` — Cancel appointment, pending reminders, and remove calendar event (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/complete` — Complete appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/no-show` — Mark appointment no-show (Staff/Admin/Owner)

### Human Handoff & Escalation (CHUNK 8)
* `GET /api/v1/whatsapp/handoffs` — List pending/assigned handoffs for the clinic (Staff/Admin/Owner)
* `GET /api/v1/whatsapp/handoffs/{handoff_id}` — Get handoff details (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs` — Manually escalate a conversation (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/assign` — Claim/assign handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/resolve` — Resolve handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/cancel` — Cancel handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/messages` — Send staff reply on WhatsApp (Staff/Admin/Owner)

### WhatsApp Cloud API Integration (CHUNK 6A - 6E, CHUNK 7)
* `GET /api/v1/whatsapp/webhook` — Meta Webhook verification handshake (plain text challenge)
* `POST /api/v1/whatsapp/webhook` — Meta Webhook event ingestion, lead extraction & AI response dispatch
* `POST /api/v1/whatsapp/accounts` — Configure clinic WhatsApp account (Owner/Admin)
* `GET /api/v1/whatsapp/accounts` — List clinic WhatsApp accounts (Owner/Admin)
* `GET /api/v1/whatsapp/accounts/{account_id}` — View WhatsApp account details (Owner/Admin)
* `PATCH /api/v1/whatsapp/accounts/{account_id}` — Update credentials / display name (Owner/Admin)
* `DELETE /api/v1/whatsapp/accounts/{account_id}` — Deactivate integration preserving history (Owner/Admin)

---

## 5. How to Run the Backend & Test Suite

1. **Install Dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Run Full Test Suite (216 tests):**
   ```bash
   pytest -v
   ```

3. **Start Development Server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 6. How to Run the Frontend

```bash
cd frontend
npm install
npm run dev
```
