# AI Receptionist — WhatsApp AI Receptionist for Clinics

> **Current Project Status: CHUNK 10 (Clinic Staff Dashboard Expansion Completed)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, resilient AI Receptionist Engine (Gemini Primary + Groq Fallback), per-clinic WhatsApp Account Management, Meta Webhook verification & HMAC security, customer message ingestion, outbound WhatsApp AI reply dispatching via Meta Graph API, automated structured Lead Extraction & Qualification, Human Handoff Escalation, Appointment Booking System, and Clinic Staff Single-Pane Operations Dashboard.
> **Current Project Status: CHUNK 11 (Notifications & Appointment Reminders Completed)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, resilient AI Receptionist Engine (Gemini Primary + Groq Fallback), per-clinic WhatsApp Account Management, Meta Webhook verification & HMAC security, customer message ingestion, outbound WhatsApp AI reply dispatching via Meta Graph API, automated structured Lead Extraction & Qualification, Human Handoff Escalation, Appointment Booking System, Clinic Staff Dashboard, and Automated WhatsApp Appointment Notifications & Reminders (24h & 2h).

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
* Clinic staff dashboard and appointment management interface

---

## 2. Complete WhatsApp AI & Appointment Pipeline

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
               │                         AUTOMATED REMINDERS
               │                         (24h & 2h via WhatsApp)
               │                                 │
               └──────────────────────┬──────────┘
                                      ▼
                              PATIENT VISIT
                               PATIENT VISIT
                                      │
                                      ▼
                                  COMPLETED
```

---

## 3. Technology Stack

### Backend
* **Language:** Python 3.11+
* **Framework:** FastAPI (Lifespan context manager)
* **Framework:** FastAPI (Lifespan context manager + Background Reminder Scheduler)
* **AI Providers:** Google Gemini API (Primary) & Groq API (Fallback)
* **Integrations:** Meta WhatsApp Cloud API (Graph API `v20.0`)
* **Security:** Argon2id (`argon2-cffi`), PyJWT, HMAC-SHA256
* **Validation & Settings:** Pydantic v2 & Pydantic Settings
* **Database ORM:** SQLAlchemy 2.0
* **Migrations:** Alembic
* **Driver:** psycopg2-binary
* **Testing:** Pytest & HTTPX
* **ASGI Server:** Uvicorn

### Frontend
* **Framework:** Next.js 14+ (App Router)
* **Language:** TypeScript (Strict Mode)
* **Styling:** Tailwind CSS + PostCSS
* **Icons:** Lucide React

---

## 4. API Endpoints (v1)

### Appointment Management (CHUNK 9)
### Appointment & Reminder Management (CHUNK 9 & CHUNK 11)
* `GET /api/v1/appointments` — List appointments with pagination and filters (`status`, `lead_id`, `conversation_id`, `date`, `date_from`, `date_to`)
* `POST /api/v1/appointments` — Create appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments` — Create appointment and auto-schedule 24h/2h reminders (Staff/Admin/Owner)
* `GET /api/v1/appointments/{appointment_id}` — Get appointment details (Staff/Admin/Owner)
* `PATCH /api/v1/appointments/{appointment_id}` — Update appointment details (Staff/Admin/Owner)
* `GET /api/v1/appointments/{appointment_id}/reminders` — Get reminder delivery logs and statuses (Staff/Admin/Owner)
* `PATCH /api/v1/appointments/{appointment_id}` — Update appointment details / reschedule reminders (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/confirm` — Confirm appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/cancel` — Cancel appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/complete` — Complete appointment (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/no-show` — Mark appointment no-show (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/cancel` — Cancel appointment and cancel pending reminders (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/complete` — Complete appointment and cancel pending reminders (Staff/Admin/Owner)
* `POST /api/v1/appointments/{appointment_id}/no-show` — Mark appointment no-show and cancel pending reminders (Staff/Admin/Owner)


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

2. **Run Full Test Suite:**
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
