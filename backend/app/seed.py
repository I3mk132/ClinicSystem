"""
Seed script - creates the database tables (if missing) and populates:
  - a default admin account (from .env FIRST_ADMIN_* values)
  - a few example departments & doctors with weekly working hours

Run with:
    python -m app.seed

Safe to re-run: it skips anything that already exists.
"""
from datetime import time

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import generate_api_key, hash_password
from app.models.api_key import ApiKey
from app.models.clinic import Clinic
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorAvailability
from app.models.section import ClinicSection, SectionKind
from app.models.user import User, UserRole

# Slug of the tenant everything seeded here belongs to. The frontend's
# CLINIC_SLUG (added in Session 2b) must match this to talk to the demo data.
DEMO_CLINIC_SLUG = "demo"


def seed_clinic(db) -> Clinic:
    """Get-or-create the demo tenant that owns every seeded row."""
    clinic = db.query(Clinic).filter(Clinic.slug == DEMO_CLINIC_SLUG).first()
    if clinic:
        print(f"[seed] Clinic '{DEMO_CLINIC_SLUG}' already exists - skipping.")
        return clinic
    # Seed a demo theme override so the out-of-the-box deployment shows real
    # bilingual branding (and demonstrates Session 3 theming). The frontend's
    # config.js name/logo are only a fallback for when no theme is served.
    clinic = Clinic(
        slug=DEMO_CLINIC_SLUG,
        name="Demo Clinic",
        is_active=True,
        theme_preset="default",
        theme_overrides={
            "name": {"ar": "عيادة ديجيفو الطبية", "tr": "dijivoo Klinik"},
            "hero": {
                "title": {"ar": "رعاية صحية بموعد واحد", "tr": "Tek randevuyla sağlık"},
            },
        },
    )
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    print(f"[seed] Created clinic (tenant) -> slug='{DEMO_CLINIC_SLUG}' id={clinic.id}")
    return clinic


def seed_superadmin(db):
    """The global developer account (clinic_id NULL). Manages clinics via /superadmin/*."""
    existing = (
        db.query(User)
        .filter(User.role == UserRole.SUPERADMIN, User.email == settings.SUPERADMIN_EMAIL)
        .first()
    )
    if existing:
        print(f"[seed] Superadmin '{settings.SUPERADMIN_EMAIL}' already exists - skipping.")
        return
    superadmin = User(
        clinic_id=None,  # global - not tied to any clinic
        full_name=settings.SUPERADMIN_NAME,
        email=settings.SUPERADMIN_EMAIL,
        hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
        role=UserRole.SUPERADMIN,
        preferred_language="ar",
        is_verified=True,
    )
    db.add(superadmin)
    db.commit()
    print(f"[seed] Created superadmin account -> {settings.SUPERADMIN_EMAIL} / {settings.SUPERADMIN_PASSWORD}")


def seed_admin(db, clinic: Clinic):
    existing = db.query(User).filter(User.email == settings.FIRST_ADMIN_EMAIL).first()
    if existing:
        print(f"[seed] Admin '{settings.FIRST_ADMIN_EMAIL}' already exists - skipping.")
        return
    admin = User(
        clinic_id=clinic.id,
        full_name=settings.FIRST_ADMIN_NAME,
        email=settings.FIRST_ADMIN_EMAIL,
        hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        preferred_language="ar",
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    print(f"[seed] Created admin account -> {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")


def seed_demo_data(db, clinic: Clinic):
    if db.query(Department).count() > 0:
        print("[seed] Departments already exist - skipping demo data.")
        return

    departments_data = [
        dict(
            name_ar="طب الأسنان", name_tr="Diş Hekimliği",
            description_ar="علاج وتجميل الأسنان لجميع الأعمار.",
            description_tr="Her yaş için diş tedavisi ve estetik diş hekimliği.",
            icon="tooth",
        ),
        dict(
            name_ar="الجلدية والتجميل", name_tr="Cildiye ve Estetik",
            description_ar="تشخيص وعلاج أمراض الجلد والعناية التجميلية.",
            description_tr="Cilt hastalıklarının tanı ve tedavisi, estetik bakım.",
            icon="sparkles",
        ),
        dict(
            name_ar="طب الأطفال", name_tr="Çocuk Sağlığı",
            description_ar="متابعة نمو وصحة الأطفال منذ الولادة.",
            description_tr="Doğumdan itibaren çocuk sağlığı ve gelişim takibi.",
            icon="baby",
        ),
        dict(
            name_ar="العظام والمفاصل", name_tr="Ortopedi",
            description_ar="علاج إصابات وأمراض العظام والمفاصل والعضلات.",
            description_tr="Kemik, eklem ve kas hastalıklarının tedavisi.",
            icon="bone",
        ),
    ]
    departments = []
    for data in departments_data:
        dept = Department(clinic_id=clinic.id, **data)
        db.add(dept)
        departments.append(dept)
    db.commit()
    for dept in departments:
        db.refresh(dept)

    doctors_data = [
        dict(full_name="Dr. Layla Hassan", title_ar="استشارية طب أسنان", title_tr="Diş Hekimliği Uzmanı",
             bio_ar="خبرة 12 عامًا في طب وتجميل الأسنان.", bio_tr="Diş hekimliğinde 12 yıllık deneyim.",
             department=departments[0]),
        dict(full_name="Dr. Emre Yıldız", title_ar="أخصائي جلدية", title_tr="Cildiye Uzmanı",
             bio_ar="متخصص في علاج حب الشباب والتقشير الكيميائي.", bio_tr="Akne tedavisi ve kimyasal peeling uzmanı.",
             department=departments[1]),
        dict(full_name="Dr. Sara Al-Amin", title_ar="استشارية طب أطفال", title_tr="Çocuk Sağlığı Uzmanı",
             bio_ar="متابعة نمو الأطفال والتطعيمات.", bio_tr="Çocuk gelişimi ve aşı takibi.",
             department=departments[2]),
        dict(full_name="Dr. Mehmet Kaya", title_ar="استشاري عظام", title_tr="Ortopedi Uzmanı",
             bio_ar="متخصص في إصابات الرياضة وجراحة المفاصل.", bio_tr="Spor yaralanmaları ve eklem cerrahisi uzmanı.",
             department=departments[3]),
    ]

    for data in doctors_data:
        department = data.pop("department")
        doctor = Doctor(clinic_id=clinic.id, department_id=department.id, **data)
        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        # Sunday(6) & Tuesday(1) mornings, Thursday(3) afternoons (weekday: 0=Monday ... 6=Sunday)
        db.add_all(
            [
                DoctorAvailability(
                    clinic_id=clinic.id, doctor_id=doctor.id, weekday=6, start_time=time(9, 0),
                    end_time=time(13, 0), slot_duration_minutes=30,
                ),
                DoctorAvailability(
                    clinic_id=clinic.id, doctor_id=doctor.id, weekday=1, start_time=time(9, 0),
                    end_time=time(13, 0), slot_duration_minutes=30,
                ),
                DoctorAvailability(
                    clinic_id=clinic.id, doctor_id=doctor.id, weekday=3, start_time=time(14, 0),
                    end_time=time(18, 0), slot_duration_minutes=20,
                ),
            ]
        )
    db.commit()
    print(f"[seed] Created {len(departments)} departments and {len(doctors_data)} doctors with weekly schedules.")


def seed_demo_sections(db, clinic: Clinic):
    """A text-only welcome section so a fresh demo homepage isn't empty. Image
    sections need real R2 uploads (see the admin Media panel), so we seed no
    images here - the section renders fine without them."""
    if db.query(ClinicSection).filter(ClinicSection.clinic_id == clinic.id).count() > 0:
        print("[seed] Homepage sections already exist - skipping.")
        return
    db.add(
        ClinicSection(
            clinic_id=clinic.id,
            kind=SectionKind.CUSTOM,
            title_ar="لماذا تختار عيادتنا؟",
            title_tr="Neden bizi seçmelisiniz?",
            body_ar="فريق طبي متخصص، أحدث الأجهزة، وحجز موعدك في خطوة واحدة عبر الإنترنت.",
            body_tr="Uzman sağlık ekibi, en yeni cihazlar ve tek adımda çevrimiçi randevu.",
            sort_order=0,
            is_active=True,
        )
    )
    db.commit()
    print("[seed] Created a demo homepage section.")


def seed_demo_api_key(db, clinic: Clinic):
    if db.query(ApiKey).count() > 0:
        print("[seed] An API key already exists - skipping demo key.")
        return
    raw_key, hashed, prefix = generate_api_key()
    db.add(ApiKey(clinic_id=clinic.id, name="Demo Integration Key", hashed_key=hashed, key_prefix=prefix))
    db.commit()
    print(f"[seed] Created a demo API key for bot/system integrations -> {raw_key}")
    print("[seed] (Shown once - save it now. Manage/revoke keys from Admin > Integrations, or create new ones there.)")
    try:
        with open("./.demo_api_key.txt", "w") as f:
            f.write(raw_key + "\n")
        print("[seed] Also saved to backend/.demo_api_key.txt for convenience during local development.")
    except OSError:
        pass


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_superadmin(db)
        clinic = seed_clinic(db)
        seed_admin(db, clinic)
        if settings.SEED_DEMO_DATA:
            seed_demo_data(db, clinic)
            seed_demo_sections(db, clinic)
            seed_demo_api_key(db, clinic)
        else:
            print("[seed] SEED_DEMO_DATA=false - skipping demo departments/doctors/API key.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
