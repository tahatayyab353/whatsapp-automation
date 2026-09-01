# AI Receptionist — System Documentation

## 1. Overview
**AI Receptionist** is a production-oriented multi-tenant SaaS platform designed for dental and aesthetic clinics in Karachi, Pakistan.
It automates patient inquiries, FAQs, appointment requests, service explanations, lead qualification, and clinic escalations via WhatsApp.

---

## 2. Architecture & Multi-Tenancy

### 2.1 Core Multi-Tenancy Principles
* **Tenant Definition:** A tenant represents an independent **Clinic**.
* **Tenant Scoping:** Every tenant-owned record contains a mandatory `clinic_id` foreign key referencing `clinics.id`.
* **Platform vs. Tenant Entities:**
  * `User`: Platform-level entity. A user can belong to multiple clinics under distinct roles (e.g. `owner`, `admin`, `staff`) via `ClinicMembership`.
  * `ClinicMembership`: Tenant-scoped link associating a `User` with a `Clinic`. Enforces `UNIQUE(clinic_id, user_id)`.
  * Tenant-Owned: `Lead`, `Conversation`, `Message`, `Appointment`, `KnowledgeDocument`, `WhatsAppAccount`.
* **UUID Identifiers:** All entities use UUID primary keys (`Uuid(as_uuid=True)`).
* **Timezone Awareness:** All timestamps are timezone-aware (`DateTime(timezone=True)` UTC) with clinic-specific operating timezones (default `Asia/Karachi`).

---

## 3. AI Receptionist Engine (CHUNK 5 & CHUNK 6D)

### 3.1 Dual-Provider Architecture (Gemini Primary + Groq Fallback)

```text
Customer WhatsApp Message
            │
            ▼
POST /api/v1/whatsapp/webhook (HMAC-SHA256 Verified)
            │
            ▼
Message Ingestion Pipeline (6C)
            ├── 1. Resolve WhatsAppAccount & Clinic
            ├── 2. Resolve/Create Lead
            ├── 3. Resolve/Create Conversation
            └── 4. Persist Customer Message & Commit
            │
            ▼
AI Receptionist Orchestration (6D)
            ├── 1. Tenant-scoped Active Knowledge Lookup (clinic_id == clinic.id)
            ├── 2. Bounded Conversation History (last 20 messages)
            ├── 3. Patient Lead Context Lookup
            └── 4. Structured System Prompt Synthesis (Anti-Prompt-Injection)
            │
            ▼
Primary Provider: Google Gemini API (gemini-1.5-flash)
            │
       ┌────┴────┐
       │         │
    SUCCESS   RETRYABLE (Timeout / 429 / 5xx)
       │         │
       │         ▼
       │      Fallback Provider: Groq API (llama-3.3-70b-versatile)
       │         │
       └────┬────┘
            ▼
     Generated AI Response
            │
            ▼
Meta WhatsApp Cloud API (`POST /messages`)
            │
            ▼
Customer receives WhatsApp reply
            │
            ▼
Persist AI Message (`sender_type='ai'`, `external_message_id=wamid.OUTBOUND...`) & Commit
```

---

## 4. WhatsApp Cloud API Architecture & Security

### 4.1 Meta Cloud API Tenant Routing & Outbound Flow

```text
Incoming Webhook:
Meta Event ──► HMAC-SHA256 Validation ──► phone_number_id ──► WhatsAppAccount ──► Clinic Context

Outbound Reply:
Clinic Context ──► WhatsAppAccount.access_token ──► Meta Graph API (/v20.0/{phone_number_id}/messages) ──► Customer Phone
```

### 4.2 Database Transaction Boundaries

* **Customer Ingestion Transaction:** Ingests and commits the customer message first so history is immediately recorded.
* **External Calls (No DB Locks):** Calls AI providers (Gemini / Groq) and Meta Graph API with zero open database transaction locks.
* **Outbound Persistence Transaction:** Creates and commits the AI response message and updates `conversation.last_message_at`.

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
- **CHUNK 6E**: End-to-End Hardening & Testing *(Pending)*
- **CHUNK 7**: Clinic Staff Dashboard UI & Live Chat CRM *(Pending)*
- **CHUNK 8**: Production Hardening, PostgreSQL RLS & Deployment *(Pending)*
