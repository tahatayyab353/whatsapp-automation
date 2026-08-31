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

## 3. AI Receptionist Engine (CHUNK 5)

### 3.1 Dual-Provider Architecture (Gemini Primary + Groq Fallback)

```text
Customer Message
      │
      ▼
ReceptionistService
      ├── 1. Tenant-scoped Active Knowledge Lookup (clinic_id == clinic.id)
      ├── 2. Bounded Conversation History (last 20 messages)
      ├── 3. Patient Lead Context Lookup
      └── 4. Structured System Prompt Synthesis (Anti-Prompt-Injection)
      │
      ▼
Primary Provider: Google Gemini API (gemini-1.5-flash)
      │
      ├── [SUCCESS] ───────────────────────────► Returns AI Response
      │
      └── [RETRYABLE FAILURE] (Timeout / 429 RateLimit / 5xx Server Error)
              │
              ▼
      Fallback Provider: Groq API (llama-3.3-70b-versatile)
              │
              ├── [SUCCESS] ───────────────────► Returns AI Response (provider='groq')
              └── [FAILURE] ───────────────────► Controlled 503 AI_SERVICE_UNAVAILABLE
```

### 3.2 Failure Classification & Routing Policy

| Error Type | Trigger Conditions | Action |
| :--- | :--- | :--- |
| `AIProviderTimeoutError` | Provider request exceeds `AI_REQUEST_TIMEOUT_SECONDS` (20s) | **Triggers Fallback** |
| `AIRateLimitError` | Provider returns HTTP 429 Too Many Requests | **Triggers Fallback** |
| `AITemporaryServerError` | Provider returns HTTP 500, 502, 503, 504 | **Triggers Fallback** |
| `AIAuthenticationError` | Invalid or expired API Key (HTTP 401 / 403) | **No Fallback** (Fails directly) |
| `AIConfigurationError` | Missing required provider settings | **No Fallback** (Fails directly) |
| `AIInvalidResponseError` | Empty response or blocked by safety filter | **Controlled Error** |

---

### 3.3 Knowledge & Cost-Control Boundaries

* **Knowledge Scope:** Only documents where `clinic_id == active_clinic.id` and `is_active == True` are ingested.
* **Document Limit:** `MAX_KNOWLEDGE_DOCUMENTS = 10`
* **Character Budget:** `MAX_KNOWLEDGE_CHARS = 12000`
* **Conversation History:** `RECENT_MESSAGE_LIMIT = 20`
* **Output Token Cap:** `AI_MAX_OUTPUT_TOKENS = 500`
* **Temperature:** `AI_TEMPERATURE = 0.2` (Conservative, factual responses)

---

### 3.4 Prompt Injection Resistance & Safety

1. **Untrusted Data Boundary:** All knowledge base text and customer messages are explicitly designated as untrusted data in the system instructions.
2. **No Hallucinated Bookings:** The model is prohibited from claiming an appointment is confirmed or payment received unless confirmed by the core application.
3. **Conservative Medical Advice:** The model provides general clinic descriptions and pricing, deferring diagnostic advice to clinic doctors.

---

### 3.5 Development & Testing Endpoint

* `POST /api/v1/ai/test-chat`
  * **Headers:** `Authorization: Bearer <JWT>`, `X-Clinic-ID: <UUID>`
  * **Payload:** `{"conversation_id": "...", "message": "How much for teeth whitening?"}`
  * **Behavior:** Automatically persists the customer's message and the resulting AI response message to the database with `last_message_at` updated.

---

## 4. Implementation Roadmap
- **CHUNK 0**: Project Scaffolding & Health Infrastructure *(Completed)*
- **CHUNK 1**: Backend Core, Correlation ID & API Foundation *(Completed)*
- **CHUNK 2**: Multi-Tenant Database Architecture, Models & Migrations *(Completed)*
- **CHUNK 3**: Authentication, JWT, Multi-Clinic & Role Authorization *(Completed)*
- **CHUNK 4**: Clinic Management + Lead, Conversation, Knowledge & Appointment APIs *(Completed)*
- **CHUNK 5**: AI Receptionist Engine (Gemini Primary + Groq Fallback) *(Completed)*
- **CHUNK 6**: WhatsApp Cloud API Integration & Meta Webhooks
- **CHUNK 7**: Clinic Staff Dashboard UI & Live Chat CRM
- **CHUNK 8**: Production Hardening, PostgreSQL RLS & Deployment
