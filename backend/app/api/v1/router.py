from fastapi import APIRouter
from app.api.v1.endpoints import (
    ai,
    appointments,
    auth,
    clinics,
    conversations,
    health,
    knowledge,
    leads,
    members,
    messages,
    system,
)

api_router = APIRouter()

# Authentication & Current User
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Health & Diagnostics
api_router.include_router(health.router, tags=["Health"])

# System Information
api_router.include_router(system.router, tags=["System"])

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
