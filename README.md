# AI Receptionist — WhatsApp AI Receptionist for Clinics

> **Current Project Status: CHUNK 8 (Human Handoff & Escalation System Completed)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, resilient AI Receptionist Engine (Gemini Primary + Groq Fallback), per-clinic WhatsApp Account Management, Meta Webhook verification & HMAC security, customer message ingestion, outbound WhatsApp AI reply dispatching via Meta Graph API, automated structured Lead Extraction & Qualification, and Human Handoff & Escalation Queue.

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
* Appointment request intake and scheduling
* Clinic staff dashboard and conversation analytics

---

## 2. Complete WhatsApp AI & Human Handoff Pipeline

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
               │             NORMAL          ESCALATE
               │                │                │
               │                ▼                ▼
               │           AI RESPONSE     HANDOFF CREATED
               │                                 │
               │                                 ▼
               │                         ┌───────────────┐
               │                         │ STAFF QUEUE   │
               │                         └───────┬───────┘
               │                                 │
               │                              CLAIM
               │                                 │
               └──────────────────────┬──────────┘
                                      ▼
                              HUMAN CONVERSATION
                                      │
                                      ▼
                                   RESOLVE
```

---

## 3. Technology Stack

### Backend
* **Language:** Python 3.11+
* **Framework:** FastAPI (Lifespan context manager)
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

### AI Receptionist
* `POST /api/v1/ai/test-chat` — Execute AI receptionist completion on a conversation (persists messages)

### Authentication & Profile
* `POST /api/v1/auth/login` — User login returning JWT access token
* `GET /api/v1/auth/me` — Current user profile

### Clinic & Member Management
* `GET /api/v1/clinics/me` — Clinic profile
* `PATCH /api/v1/clinics/me` — Update clinic profile
* `GET /api/v1/members` — List clinic members
* `PATCH /api/v1/members/{user_id}/role` — Update member role
* `DELETE /api/v1/members/{user_id}` — Remove member from clinic

### Leads, Conversations & Knowledge
* `POST /api/v1/leads` — Create patient lead
* `GET /api/v1/leads` — List & filter leads
* `POST /api/v1/conversations` — Start conversation thread
* `GET /api/v1/conversations` — List conversations
* `POST /api/v1/conversations/{conv_id}/messages` — Send message
* `GET /api/v1/conversations/{conv_id}/messages` — List messages chronologically
* `POST /api/v1/knowledge` — Create knowledge doc
* `GET /api/v1/knowledge` — List knowledge docs
* `POST /api/v1/appointments` — Schedule patient appointment
* `GET /api/v1/appointments` — List appointments

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
