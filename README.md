# AI Receptionist — WhatsApp AI Receptionist for Clinics

> **Current Project Status: CHUNK 6D (AI Receptionist + Outbound WhatsApp Messaging Pipeline Completed)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, resilient AI Receptionist Engine (Gemini Primary + Groq Fallback), per-clinic WhatsApp Account Management, Meta Webhook verification & HMAC security, customer message ingestion, and automated outbound WhatsApp AI reply dispatching via Meta Graph API.

---

## 1. What the Project Is

**AI Receptionist** is a production-oriented SaaS platform engineered for **dental and aesthetic clinics in Karachi, Pakistan**.

The product enables clinics to automate patient communication through WhatsApp, offering:
* AI-driven answers to clinic-approved FAQs
* Service and pricing explanations
* Clinic information (hours, location, practitioner details)
* Patient lead capture and automated qualification
* Appointment request intake and scheduling
* Seamless escalation to human front-desk staff
* Automated follow-ups and appointment reminders
* Clinic staff dashboard and conversation analytics

---

## 2. Complete WhatsApp AI Flow

```text
Customer sends WhatsApp message
            │
            ▼
POST /api/v1/whatsapp/webhook (HMAC-SHA256 Verified)
            │
            ▼
Message Ingestion Pipeline
            ├── Resolve WhatsAppAccount & Clinic
            ├── Resolve/Create Lead
            ├── Resolve/Create Conversation
            └── Persist Customer Message & Commit
            │
            ▼
AI Receptionist Orchestration
            ├── Grounded Knowledge Retrieval
            ├── Conversation History (Last 20 messages)
            └── Anti-Prompt-Injection System Instructions
            │
            ▼
Primary AI: Gemini 1.5 Flash (Fallback: Groq LLaMA 3.3 70B)
            │
            ▼
Meta WhatsApp Cloud API (Outbound Send via Graph API v20.0)
            │
            ▼
Customer receives WhatsApp response
            │
            ▼
Persist AI Message (external_message_id = Meta Message ID) & Commit
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

### WhatsApp Cloud API Integration (CHUNK 6A - 6D)
* `GET /api/v1/whatsapp/webhook` — Meta Webhook verification handshake (plain text challenge)
* `POST /api/v1/whatsapp/webhook` — Meta Webhook event ingestion & AI response dispatch
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
