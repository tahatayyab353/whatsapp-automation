import uuid
from datetime import date, datetime, time, timezone
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models import Appointment, Clinic, Conversation, Handoff, Lead, Message, User
from app.models.base import utc_now
from app.schemas.dashboard import (
    DashboardAppointmentItem,
    DashboardConversationItem,
    DashboardHandoffItem,
    DashboardLeadItem,
    DashboardMetrics,
    DashboardSummaryResponse,
)


class DashboardService:
    """
    Tenant-scoped dashboard aggregation service.
    Computes key clinic operational metrics and retrieves today's appointments,
    pending handoff escalations, recent conversations, and leads.
    """

    @classmethod
    def get_summary(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
    ) -> DashboardSummaryResponse:
        clinic = db.scalar(select(Clinic).where(Clinic.id == clinic_id))
        if not clinic:
            raise NotFoundException("Clinic not found.")

        # Compute today's UTC boundaries
        now = utc_now()
        today_date = now.date()
        today_start = datetime.combine(today_date, time.min, tzinfo=timezone.utc)
        today_end = datetime.combine(today_date, time.max, tzinfo=timezone.utc)

        # 1. Metrics Aggregations
        total_leads = db.scalar(
            select(func.count(Lead.id)).where(Lead.clinic_id == clinic_id)
        ) or 0

        open_conversations = db.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.clinic_id == clinic_id,
                Conversation.status.in_(["open", "human_required"]),
            )
        ) or 0

        pending_handoffs_count = db.scalar(
            select(func.count(Handoff.id)).where(
                Handoff.clinic_id == clinic_id,
                Handoff.status == "pending",
            )
        ) or 0

        today_appointments_count = db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.clinic_id == clinic_id,
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at <= today_end,
            )
        ) or 0

        confirmed_today_count = db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.clinic_id == clinic_id,
                Appointment.status == "confirmed",
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at <= today_end,
            )
        ) or 0

        completed_today_count = db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.clinic_id == clinic_id,
                Appointment.status == "completed",
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at <= today_end,
            )
        ) or 0

        new_leads_today_count = db.scalar(
            select(func.count(Lead.id)).where(
                Lead.clinic_id == clinic_id,
                Lead.created_at >= today_start,
            )
        ) or 0

        metrics = DashboardMetrics(
            total_leads=total_leads,
            open_conversations=open_conversations,
            pending_handoffs=pending_handoffs_count,
            today_appointments=today_appointments_count,
            confirmed_appointments_today=confirmed_today_count,
            completed_appointments_today=completed_today_count,
            new_leads_today=new_leads_today_count,
        )

        # 2. Today's Appointments with Lead info
        appts_query = (
            select(Appointment)
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at <= today_end,
            )
            .order_by(Appointment.scheduled_at.asc())
            .limit(20)
        )
        today_appts_raw = db.scalars(appts_query).all()
        today_appointments_list: List[DashboardAppointmentItem] = []
        for appt in today_appts_raw:
            lead = db.scalar(select(Lead).where(Lead.id == appt.lead_id, Lead.clinic_id == clinic_id)) if appt.lead_id else None
            today_appointments_list.append(
                DashboardAppointmentItem(
                    id=appt.id,
                    lead_id=appt.lead_id,
                    lead_name=lead.full_name if lead else None,
                    lead_phone=lead.phone if lead else None,
                    title=appt.title,
                    scheduled_at=appt.scheduled_at,
                    duration_minutes=appt.duration_minutes,
                    status=appt.status,
                    notes=appt.notes,
                )
            )

        # 3. Active Handoffs (pending or assigned)
        handoffs_query = (
            select(Handoff)
            .where(
                Handoff.clinic_id == clinic_id,
                Handoff.status.in_(["pending", "assigned"]),
            )
            .order_by(Handoff.requested_at.desc())
            .limit(10)
        )
        active_handoffs_raw = db.scalars(handoffs_query).all()
        pending_handoffs_list: List[DashboardHandoffItem] = []
        for h in active_handoffs_raw:
            lead = db.scalar(select(Lead).where(Lead.id == h.lead_id, Lead.clinic_id == clinic_id)) if h.lead_id else None
            assignee = db.scalar(select(User).where(User.id == h.assigned_to_user_id)) if h.assigned_to_user_id else None
            pending_handoffs_list.append(
                DashboardHandoffItem(
                    id=h.id,
                    conversation_id=h.conversation_id,
                    lead_id=h.lead_id,
                    lead_name=lead.full_name if lead else None,
                    lead_phone=lead.phone if lead else None,
                    reason=h.reason,
                    status=h.status,
                    notes=h.notes,
                    requested_at=h.requested_at,
                    assigned_to_user_id=h.assigned_to_user_id,
                    assigned_to_name=assignee.full_name if assignee else None,
                )
            )

        # 4. Recent Conversations
        convs_query = (
            select(Conversation)
            .where(Conversation.clinic_id == clinic_id)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
            .limit(10)
        )
        convs_raw = db.scalars(convs_query).all()
        recent_conversations_list: List[DashboardConversationItem] = []
        for c in convs_raw:
            lead = db.scalar(select(Lead).where(Lead.id == c.lead_id, Lead.clinic_id == clinic_id)) if c.lead_id else None
            latest_msg = db.scalar(
                select(Message)
                .where(Message.conversation_id == c.id, Message.clinic_id == clinic_id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            preview = None
            if latest_msg and latest_msg.content:
                preview = latest_msg.content[:80] + ("..." if len(latest_msg.content) > 80 else "")

            recent_conversations_list.append(
                DashboardConversationItem(
                    id=c.id,
                    lead_id=c.lead_id,
                    lead_name=lead.full_name if lead else None,
                    lead_phone=lead.phone if lead else None,
                    channel=c.channel,
                    status=c.status,
                    last_message_at=c.last_message_at,
                    last_message_preview=preview,
                )
            )

        # 5. Recent Leads
        leads_query = (
            select(Lead)
            .where(Lead.clinic_id == clinic_id)
            .order_by(Lead.created_at.desc())
            .limit(10)
        )
        leads_raw = db.scalars(leads_query).all()
        recent_leads_list = [
            DashboardLeadItem(
                id=l.id,
                full_name=l.full_name,
                phone=l.phone,
                email=l.email,
                status=l.status,
                service_interest=l.service_interest,
                created_at=l.created_at,
            )
            for l in leads_raw
        ]

        return DashboardSummaryResponse(
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            timezone=clinic.timezone,
            metrics=metrics,
            today_appointments=today_appointments_list,
            pending_handoffs=pending_handoffs_list,
            recent_conversations=recent_conversations_list,
            recent_leads=recent_leads_list,
        )


dashboard_service = DashboardService()

