# AI Receptionist — WhatsApp AI Receptionist for Clinics

> **Current Project Status: CHUNK 5 (AI Engine: Gemini Primary + Groq Fallback)**  
> This repository contains the complete foundation, API core, multi-tenant database models, JWT authentication, business REST APIs, and resilient AI Receptionist Engine with Gemini primary and Groq fallback. WhatsApp webhooks and dashboard UI are scheduled for subsequent chunks.

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

## 2. AI Architecture & Fallback Flow

```text
Customer Message
      ↓
Receptionist Service (Knowledge Lookup + History + System Rules)
      ↓
Primary Provider: Google Gemini API (gemini-1.5-flash)
      │
      ├── [SUCCESS] ───────────────────────► Returns AI Response
      │
      └── [RETRYABLE FAILURE] (Timeout / 429 RateLimit / 5xx Server Error)
              ↓
          Fallback Provider: Groq API (llama-3.3-70b-versatile)
              ↓
          Returns AI Response (provider="groq")
```

---

## 3. Technology Stack

### Backend
* **Language:** Python 3.11+
* **Framework:** FastAPI (Lifespan context manager)
* **AI Providers:** Google Gemini API (Primary) & Groq API (Fallback)
* **Security:** Argon2id (`argon2-cffi`), PyJWT
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

## 5. Development Credentials & Seeding

Run the idempotent database seeder:
```bash
python scripts/seed_dev.py
```

### Pre-seeded Development Accounts:
* **Clinic Owner:** `owner@demo.local` / `DemoOwner123!` (Role: `owner` in Demo Dental Clinic)
* **Clinic Admin:** `admin@demo.local` / `DemoAdmin123!` (Role: `admin` in Demo Dental Clinic)
* **Front Desk Staff:** `staff@demo.local` / `DemoStaff123!` (Role: `staff` in Demo Dental Clinic)

---

## 6. How to Run the Backend & Test Suite

1. **Install Dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Run Migrations & Seed:**
   ```bash
   alembic upgrade head
   python scripts/seed_dev.py
   ```

3. **Run Test Suite:**
   ```bash
   pytest -v
   ```

4. **Start Development Server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 7. How to Run the Frontend

```bash
cd frontend
npm install
npm run dev
```
