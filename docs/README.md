# AI Receptionist — System Documentation

## 1. Overview
**AI Receptionist** is a production-oriented multi-tenant SaaS platform designed for dental and aesthetic clinics in Karachi, Pakistan.
It automates patient inquiries, FAQs, appointment requests, service explanations, lead extraction & qualification, and human staff escalation via WhatsApp.

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

## 3. WhatsApp & AI Pipeline (Chunks 6A–6E, 7 & 8)

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

## 4. Human Handoff & Escalation Lifecycle (Chunk 8)

### 4.1 State Machine
```text
                 ┌──────────────┐
                 │ AI ACTIVE    │ (conversation.status = 'open')
                 └──────┬───────┘
                        │
                 escalation (explicit request, complaint, ai uncertainty)
                        │
                        ▼
              ┌──────────────────┐
              │ HUMAN REQUESTED  │ (handoff.status = 'pending', conversation.status = 'human_required')
              └────────┬─────────┘
                       │
                    assign (staff claims handoff)
                       │
                       ▼
              ┌──────────────────┐
              │ HUMAN ACTIVE     │ (handoff.status = 'assigned', assigned_to_user_id = user.id)
              └────────┬─────────┘
                       │
                    resolve (staff finishes inquiry)
                       │
                       ▼
              ┌──────────────────┐
              │ RESOLVED         │ (handoff.status = 'resolved', conversation.status = 'open')
              └──────────────────┘
```

### 4.2 Endpoints (`/api/v1/whatsapp/handoffs`)
* `GET /api/v1/whatsapp/handoffs` — List pending/assigned handoffs for the clinic (Staff/Admin/Owner)
* `GET /api/v1/whatsapp/handoffs/{handoff_id}` — Get handoff details (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs` — Manually escalate a conversation (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/assign` — Claim/assign handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/resolve` — Resolve handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/cancel` — Cancel handoff (Staff/Admin/Owner)
* `POST /api/v1/whatsapp/handoffs/{handoff_id}/messages` — Send staff reply on WhatsApp (Staff/Admin/Owner)

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
- **CHUNK 9**: Appointment Booking & Scheduling Automation *(Pending)*
- **CHUNK 10**: Clinic Staff Dashboard UI & Live Chat CRM *(Pending)*
