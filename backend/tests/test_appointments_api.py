# API tests for appointments are fully implemented in test_appointments.py
from app.services.appointment_service import appointment_service


def test_appointment_service_instantiation():
    assert appointment_service is not None

