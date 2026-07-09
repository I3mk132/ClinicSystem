"""
Importing every model here ensures they are all registered on Base.metadata
before `Base.metadata.create_all()` is called in app.main.
"""
from app.models.user import User, UserRole, ContactMethod  # noqa: F401
from app.models.department import Department  # noqa: F401
from app.models.doctor import Doctor  # noqa: F401
from app.models.schedule import DoctorAvailability, DoctorTimeOff  # noqa: F401
from app.models.appointment import Appointment, AppointmentStatus  # noqa: F401
from app.models.verification import VerificationCode, VerificationPurpose  # noqa: F401
from app.models.api_key import ApiKey  # noqa: F401
