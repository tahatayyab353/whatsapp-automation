"""Development Database Seeder.
Populates the database with realistic sample data for local development and manual testing.
Safe to execute multiple times (idempotent).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

# Add backend directory to sys.path so app imports work when script is executed directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import (
    Appointment,
    Clinic,
    ClinicMembership,
    Conversation,
    KnowledgeDocument,
    Lead,
    Message,
    User,
    WhatsAppAccount,
)


def seed_database() -> None:
    session = SessionLocal()
    try:
        print("🌱 Starting development database seeding...")

        # 1. Seed Demo Clinic
        clinic = session.scalar(select(Clinic).where(Clinic.slug == "demo-dental-clinic"))
        if not clinic:
            clinic = Clinic(
                name="Demo Dental Clinic",
                slug="demo-dental-clinic",
                description="Premier dental and aesthetic clinic in Clifton, Karachi.",
                phone="+922135800000",
                email="info@demodental.pk",
                website="https://demodental.pk",
                timezone="Asia/Karachi",
                is_active=True,
            )
            session.add(clinic)
            session.flush()
            print(f"  ✓ Created Clinic: {clinic.name} ({clinic.id})")
        else:
            print(f"  ℹ Clinic exists: {clinic.name}")

        # 2. Seed Users (Owner, Admin, Staff) with Development Passwords
        owner_user = session.scalar(select(User).where(User.email == "owner@demo.local"))
        if not owner_user:
            owner_user = User(
                email="owner@demo.local",
                full_name="Dr. Tariq Demo",
                password_hash=hash_password("DemoOwner123!"),
                is_active=True,
                is_platform_admin=False,
            )
            session.add(owner_user)
            session.flush()
            print(f"  ✓ Created Owner User: {owner_user.email} (Password: DemoOwner123!)")
        else:
            if not owner_user.password_hash:
                owner_user.password_hash = hash_password("DemoOwner123!")
                print(f"  ✓ Updated Owner User password: {owner_user.email}")
            print(f"  ℹ Owner user exists: {owner_user.email}")

        admin_user = session.scalar(select(User).where(User.email == "admin@demo.local"))
        if not admin_user:
            admin_user = User(
                email="admin@demo.local",
                full_name="Dr. Sara Admin",
                password_hash=hash_password("DemoAdmin123!"),
                is_active=True,
                is_platform_admin=False,
            )
            session.add(admin_user)
            session.flush()
            print(f"  ✓ Created Admin User: {admin_user.email} (Password: DemoAdmin123!)")
        else:
            if not admin_user.password_hash:
                admin_user.password_hash = hash_password("DemoAdmin123!")
                print(f"  ✓ Updated Admin User password: {admin_user.email}")
            print(f"  ℹ Admin user exists: {admin_user.email}")

        staff_user = session.scalar(select(User).where(User.email == "staff@demo.local"))
        if not staff_user:
            staff_user = User(
                email="staff@demo.local",
                full_name="Ayesha Receptionist",
                password_hash=hash_password("DemoStaff123!"),
                is_active=True,
                is_platform_admin=False,
            )
            session.add(staff_user)
            session.flush()
            print(f"  ✓ Created Staff User: {staff_user.email} (Password: DemoStaff123!)")
        else:
            if not staff_user.password_hash:
                staff_user.password_hash = hash_password("DemoStaff123!")
                print(f"  ✓ Updated Staff User password: {staff_user.email}")
            print(f"  ℹ Staff user exists: {staff_user.email}")

        # 3. Seed Memberships
        owner_membership = session.scalar(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.user_id == owner_user.id,
            )
        )
        if not owner_membership:
            owner_membership = ClinicMembership(
                clinic_id=clinic.id,
                user_id=owner_user.id,
                role="owner",
            )
            session.add(owner_membership)
            print(f"  ✓ Assigned Owner role for {owner_user.email}")

        admin_membership = session.scalar(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.user_id == admin_user.id,
            )
        )
        if not admin_membership:
            admin_membership = ClinicMembership(
                clinic_id=clinic.id,
                user_id=admin_user.id,
                role="admin",
            )
            session.add(admin_membership)
            print(f"  ✓ Assigned Admin role for {admin_user.email}")

        staff_membership = session.scalar(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.user_id == staff_user.id,
            )
        )
        if not staff_membership:
            staff_membership = ClinicMembership(
                clinic_id=clinic.id,
                user_id=staff_user.id,
                role="staff",
            )
            session.add(staff_membership)
            print(f"  ✓ Assigned Staff role for {staff_user.email}")

        # 4. Seed WhatsApp Account
        wa_account = session.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.phone_number == "+923000000000"
            )
        )
        if not wa_account:
            wa_account = WhatsAppAccount(
                clinic_id=clinic.id,
                phone_number="+923000000000",
                phone_number_id="100000000000001",
                business_account_id="200000000000001",
                is_active=True,
            )
            session.add(wa_account)
            session.flush()
            print(f"  ✓ Configured WhatsApp Account: {wa_account.phone_number}")

        # 5. Seed Knowledge Documents
        docs_data = [
            {
                "title": "Clinic General FAQs",
                "category": "faq",
                "content": (
                    "Q: Where is the clinic located?\n"
                    "A: Suite 402, Al-Razi Medical Tower, Block 5, Clifton, Karachi.\n\n"
                    "Q: What are the consultation charges?\n"
                    "A: General dental checkup consultation is PKR 2,000."
                ),
            },
            {
                "title": "Services & Treatment Catalog",
                "category": "service",
                "content": (
                    "Dental Services:\n"
                    "- Professional Teeth Whitening: PKR 15,000 - 25,000\n"
                    "- Ceramic Dental Veneers: PKR 35,000 per tooth\n"
                    "- Root Canal Treatment (Single Canal): PKR 12,000\n"
                    "- Scaling & Polishing: PKR 5,000\n"
                    "- Dental Implants: From PKR 80,000"
                ),
            },
            {
                "title": "Opening Hours & Emergency Policy",
                "category": "location",
                "content": (
                    "Monday to Saturday: 11:00 AM – 8:00 PM\n"
                    "Sunday: Closed (Emergency on-call available via WhatsApp hotline)."
                ),
            },
        ]
        for doc in docs_data:
            existing_doc = session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.clinic_id == clinic.id,
                    KnowledgeDocument.title == doc["title"],
                )
            )
            if not existing_doc:
                new_doc = KnowledgeDocument(
                    clinic_id=clinic.id,
                    title=doc["title"],
                    category=doc["category"],
                    content=doc["content"],
                    is_active=True,
                )
                session.add(new_doc)
                print(f"  ✓ Seeded Knowledge Document: {doc['title']}")

        # 6. Seed Lead
        lead = session.scalar(
            select(Lead).where(
                Lead.clinic_id == clinic.id,
                Lead.phone == "+923001234567",
            )
        )
        if not lead:
            lead = Lead(
                clinic_id=clinic.id,
                full_name="Ahmed Khan",
                phone="+923001234567",
                email="ahmed.khan@example.com",
                source="whatsapp",
                status="qualified",
                service_interest="Teeth Whitening",
                notes="Patient inquiring about wedding smile makeover package.",
            )
            session.add(lead)
            session.flush()
            print(f"  ✓ Seeded Lead: {lead.full_name} ({lead.phone})")
        else:
            print(f"  ℹ Lead exists: {lead.full_name}")

        # 7. Seed Conversation & Messages
        conversation = session.scalar(
            select(Conversation).where(
                Conversation.clinic_id == clinic.id,
                Conversation.external_conversation_id == "+923001234567",
            )
        )
        if not conversation:
            conv_start = datetime.now(timezone.utc) - timedelta(hours=2)
            conversation = Conversation(
                clinic_id=clinic.id,
                lead_id=lead.id,
                channel="whatsapp",
                external_conversation_id="+923001234567",
                status="open",
                started_at=conv_start,
                last_message_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            )
            session.add(conversation)
            session.flush()

            msg1 = Message(
                clinic_id=clinic.id,
                conversation_id=conversation.id,
                sender_type="customer",
                message_type="text",
                content="Hi, I would like to know about teeth whitening services and charges.",
                external_message_id="wamid.HBgMOTIzMDAxMjM0NTY3FQIAERgSR",
                created_at=conv_start,
            )
            msg2 = Message(
                clinic_id=clinic.id,
                conversation_id=conversation.id,
                sender_type="ai",
                message_type="text",
                content=(
                    "Hello Ahmed! Welcome to Demo Dental Clinic in Karachi. "
                    "Our professional teeth whitening treatment starts from PKR 15,000. "
                    "Would you like to schedule an appointment with Dr. Tariq?"
                ),
                external_message_id="wamid.HBgMOTIzMDAxMjM0NTY3FQIAERgSA",
                created_at=conv_start + timedelta(seconds=15),
            )
            msg3 = Message(
                clinic_id=clinic.id,
                conversation_id=conversation.id,
                sender_type="customer",
                message_type="text",
                content="Yes please, do you have any slots available tomorrow afternoon?",
                external_message_id="wamid.HBgMOTIzMDAxMjM0NTY3FQIAERgSB",
                created_at=conv_start + timedelta(minutes=5),
            )
            session.add_all([msg1, msg2, msg3])
            print(f"  ✓ Seeded Conversation with 3 messages for {lead.full_name}")

        # 8. Seed Appointment
        appointment = session.scalar(
            select(Appointment).where(
                Appointment.clinic_id == clinic.id,
                Appointment.lead_id == lead.id,
            )
        )
        if not appointment:
            scheduled_time = datetime.now(timezone.utc) + timedelta(days=1, hours=4)
            appointment = Appointment(
                clinic_id=clinic.id,
                lead_id=lead.id,
                conversation_id=conversation.id if conversation else None,
                scheduled_at=scheduled_time,
                status="requested",
                notes="Patient requested 4:00 PM slot for teeth whitening consultation.",
            )
            session.add(appointment)
            print(f"  ✓ Seeded Appointment for {lead.full_name} at {scheduled_time.isoformat()}")

        session.commit()
        print("✅ Development database seeding completed successfully!")
    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
