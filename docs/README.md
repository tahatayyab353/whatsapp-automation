# AI Receptionist — System Documentation

## 1. Overview
**AI Receptionist** is a production-oriented multi-tenant SaaS platform designed for dental and aesthetic clinics in Karachi, Pakistan.
It automates patient inquiries, FAQs, appointment requests, service explanations, lead extraction & qualification, staff escalation, and appointment lifecycle management via WhatsApp.

---

## 2. Architecture & Multi-Tenancy

### 2.1 Core Multi-Tenancy Principles
* **Tenant Definition:** A tenant represents an independent **Clinic**.
* **Tenant Scoping:** Every tenant-owned record contains a mandatory `clinic_id` foreign key referencing `clinics.id`.
* **Platform vs. Tenant Entities:**
  * `User`: Platform-level entity. A user can belong to multiple clinics under distinct roles (e.g. `owner`, `admin`, `staff`) via `ClinicMembership`.
  * `ClinicMembership`: Tenant-scoped link associating a `User` with a `Clinic`. Enforces `UNIQUE(clinic_id, user_id)`.
  * Tenant-Owned: `Lead`, `Conversation`, `Message`, `Appointment`, `KnowledgeDocument`, `WhatsAppAccount`, `Handoff`.
* **UUID Identifiers:** All entities use UUID primary keys (`Uuid(as_uuid=True)`).
* **Timezone Awareness:** All timestamps are timezone-aware (`DateTime(timezone=True)` UTC) with clinic-specific operating timezones (default `Asia/Karachi`).

---

## 3. Appointment System (Chunk 9)

### 3.1 Data Model
* **Fields:** `id`, `clinic_id`, `lead_id`, `conversation_id`, `created_by_user_id`, `title`, `description`, `scheduled_at`, `duration_minutes`, `timezone`, `status`, `notes`, `cancelled_at`, `created_at`, `updated_at`.
* **Indexes:** `(clinic_id, scheduled_at)`, `(clinic_id, status)`, `(clinic_id, lead_id)`.

### 3.2 State Lifecycle & Transition Machine
```text
                 ┌──────────────┐
                 │  REQUESTED   │ (AI intake or staff booking request)
                 └──────┬───────┘
                        │
                 confirm or cancel
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
  ┌──────────────┐              ┌──────────────┐
  │  CONFIRMED   │              │  CANCELLED   │ (Terminal, records cancelled_at)
  └──────┬───────┘              └──────────────┘
         │
  complete / no-show / reschedule
         │
   ┌─────┴──────────────────┐
   ▼                        ▼
┌──────────────┐     ┌──────────────┐
│  COMPLETED   │     │   NO_SHOW    │ (Terminal states)
└──────────────┘     └──────────────┘
```

### 3.3 Endpoints (`/api/v1/appointments`)
* `GET /api/v1/appointments` — List appointments with pagination and filters (`status`, `lead_id`, `conversation_id`, `date`, `date_from`, `date_to`)
* `POST /api/v1/appointments` — Create appointment
* `GET /api/v1/appointments/{appointment_id}` — Get appointment details
* `PATCH /api/v1/appointments/{appointment_id}` — Update appointment time, duration, or notes
* `POST /api/v1/appointments/{appointment_id}/confirm` — Confirm appointment
* `POST /api/v1/appointments/{appointment_id}/cancel` — Cancel appointment
* `POST /api/v1/appointments/{appointment_id}/complete` — Mark appointment completed
* `POST /api/v1/appointments/{appointment_id}/no-show` — Mark appointment as patient no-show

---

## 4. Dashboard & Operations (Chunk 10)

### 4.1 Summary Endpoint (`/api/v1/dashboard/summary`)
* **Method:** `GET /api/v1/dashboard/summary`
* **Authorization:** `require_staff` (Requires valid JWT and `X-Clinic-ID`)
* **Response Payload (`DashboardSummaryResponse`):**
  * `metrics`: `total_leads`, `total_conversations`, `active_handoffs`, `today_appointments`, `pending_appointments`, `total_appointments`
  * `today_appointments`: List of appointments scheduled for today with lead contact details and status
  * `active_handoffs`: List of pending human handoff escalations with priority, reason, and claim actions
  * `recent_conversations`: List of active WhatsApp conversations with message counts and status
  * `recent_leads`: List of recently created/qualified leads with score, stage, and contact details

### 4.2 Frontend Single-Pane Dashboard
* Located at `/dashboard` with auto-refreshing operational metrics, appointment action buttons (confirm, complete, cancel, no-show), handoff claim/resolve triggers, and conversation feeds.

---

## 5. Implementation Roadmap
- **CHUNK 0**: Project Scaffolding & Health Infrastructure *(Completed)*
- **CHUNK 1**: Backend Core, Correlation ID & API Foundation *(Completed)*
- **CHUNK 2**: Multi-Tenant Database Architecture, Models & Migrations *(Completed)*
- **CHUNK 3**: Authentication, JWT, Multi-Clinic & Role Authorization *(Completed)*
- **CHUNK 4**: Clinic Management + Lead, Conversation, Knowledge & Appointment APIs *(Completed)*
- **CHUNK 5**: AI Receptionist Engine (Gemini Primary + Groq Fallback) *(Completed)*
- **CHUNK 6A**: WhatsApp Foundation: Data Model + Meta Configuration *(Completed)*
- **CHUNK 6B**: Webhook Verification & Security *(Completed)*
- **CHUNK 6C**: Incoming WhatsApp Message Ingestion & CRM Resolution *(Completed)*
- **CHUNK 6D**: Outbound WhatsApp + AI Receptionist Orchestration *(Completed)*
- **CHUNK 6E**: WhatsApp End-to-End Integration Hardening & Testing *(Completed)*
- **CHUNK 7**: Lead Extraction & Automatic Lead Qualification *(Completed)*
- **CHUNK 8**: Human Handoff & Escalation System *(Completed)*
- **CHUNK 9**: Appointment Booking & Scheduling System *(Completed)*
- **CHUNK 10**: Clinic Staff Dashboard Expansion *(Completed)*

