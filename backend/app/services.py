"""
Slot-generation logic.

Available time slots for a doctor on a given date are NOT stored in the
database - they are computed on the fly from:
  1) the doctor's recurring weekly `DoctorAvailability` template(s)
  2) minus any `DoctorTimeOff` for that exact date
  3) minus slots already taken by a non-cancelled `Appointment`
  4) minus slots that are already in the past (if the date is today)

This keeps the schema simple and means editing a doctor's weekly hours
instantly applies to every future date with no data migration needed.
"""
from dataclasses import dataclass
from datetime import date as date_type, datetime, time, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.schedule import DoctorAvailability, DoctorTimeOff


@dataclass
class Slot:
    start_time: time
    end_time: time
    is_available: bool


def _add_minutes(t: time, minutes: int) -> time:
    dummy = datetime.combine(date_type.today(), t) + timedelta(minutes=minutes)
    return dummy.time()


def get_slots_for_doctor_on_date(db: Session, doctor_id: int, target_date: date_type) -> List[Slot]:
    # Python's date.weekday(): Monday=0 ... Sunday=6 (matches our stored convention)
    weekday = target_date.weekday()

    templates = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.weekday == weekday,
            DoctorAvailability.is_active.is_(True),
        )
        .all()
    )
    if not templates:
        return []

    is_day_off = (
        db.query(DoctorTimeOff)
        .filter(DoctorTimeOff.doctor_id == doctor_id, DoctorTimeOff.date == target_date)
        .first()
        is not None
    )

    booked_start_times = {
        appt.start_time
        for appt in db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
    }

    now = datetime.now()
    is_today = target_date == now.date()

    slots: List[Slot] = []
    for template in templates:
        cursor = template.start_time
        while True:
            slot_end = _add_minutes(cursor, template.slot_duration_minutes)
            if slot_end > template.end_time:
                break

            is_available = True
            if is_day_off:
                is_available = False
            elif cursor in booked_start_times:
                is_available = False
            elif is_today and cursor <= now.time():
                is_available = False

            slots.append(Slot(start_time=cursor, end_time=slot_end, is_available=is_available))
            cursor = slot_end

    slots.sort(key=lambda s: s.start_time)
    return slots


def find_matching_slot(db: Session, doctor_id: int, target_date: date_type, start_time: time) -> Slot | None:
    """Used when creating a booking, to confirm the requested start_time is a real, open slot."""
    for slot in get_slots_for_doctor_on_date(db, doctor_id, target_date):
        if slot.start_time == start_time:
            return slot
    return None
