from fastapi import APIRouter
from app.api.v1.endpoints import (
    ai,
    appointments,
    auth,
    clinics,
    conversations,
    dashboard,
    handoffs,
    health,
    knowledge,
    leads,
    members,
    messages,
    system,
    whatsapp,
)

api_router = APIRouter()

# Authentication & Current User
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Health & Diagnostics
api_router.include_router(health.router, tags=["Health"])

# System Information
api_router.include_router(system.router, tags=["System"])

# Clinic Operations Dashboard
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

# Clinic Management
api_router.include_router(clinics.router, prefix="/clinics", tags=["Clinics"])

# Staff & Clinic Members
api_router.include_router(members.router, prefix="/members", tags=["Members"])

# Lead Management
api_router.include_router(leads.router, prefix="/leads", tags=["Leads"])

# Conversations & Messages
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(messages.router, prefix="/conversations", tags=["Messages"])

# Knowledge Base
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"])

# Appointment Management
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])

# AI Receptionist Engine
api_router.include_router(ai.router, prefix="/ai", tags=["AI Receptionist"])

# WhatsApp Cloud API Accounts
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["WhatsApp Integration"])

# Human Handoffs & Escalation
api_router.include_router(handoffs.router, prefix="/whatsapp", tags=["Human Handoffs"])
