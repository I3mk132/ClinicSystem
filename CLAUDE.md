# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bilingual (Arabic RTL / Turkish LTR) medical clinic appointment-booking system. Two fully decoupled halves that only talk over REST at `/api/v1`:

- `backend/` — FastAPI + SQLAlchemy. DB-agnostic (SQLite dev, PostgreSQL prod).
- `frontend/` — Static HTML/CSS/JS. **No build step, no framework, no bundler.**

The decoupling is intentional: a mobile app could replace the frontend without touching the backend.

## Commands

**Backend** (from `backend/`):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then edit SECRET_KEY, admin creds
python -m app.seed                   # create tables + admin (+ demo data unless SEED_DEMO_DATA=false)
uvicorn app.main:app --reload        # http://127.0.0.1:8000  (docs at /docs)
```

**Frontend** (from `frontend/`): any static server, e.g. `python3 -m http.server 5500`. The backend's `CORS_ORIGINS` must list the exact origin serving the frontend.

**Docker** (from `backend/`): `docker compose up -d --build`. Two services only: `clinic-api` + `cloudflared` — the DB is **external managed Postgres (Neon)**, there is no db container. Required stack env vars: `SECRET_KEY`, `DATABASE_URL` (Neon string rewritten to SQLAlchemy form `postgresql+psycopg2://…?sslmode=require`, using the pooled `-pooler` host), `FIRST_ADMIN_PASSWORD`, `TUNNEL_TOKEN`. The entrypoint runs `python -m app.seed` on every container start (idempotent). `SEED_DEMO_DATA` defaults to `false` in compose (fresh prod DB starts empty) and can be overridden from the stack environment.

**Migrations** (Alembic, from `backend/` with the venv active — URL comes from `DATABASE_URL`, no `-x` needed):

```bash
alembic upgrade head                 # apply pending migrations to the DB
alembic revision --autogenerate -m "…"  # after a model change, generate a migration
alembic downgrade -1                  # roll back one
```

On an **existing prod DB** whose pre-tenancy tables were built by `create_all()` (e.g. Neon), stamp the baseline as already-applied first, then upgrade — this applies the tenancy migrations (`0002`+`0003`), it does NOT recreate tables:

```bash
alembic stamp 0001 && alembic upgrade head
```

`0003` adds per-clinic unique constraints; if the existing data has, within one clinic, duplicate emails/phones or duplicate department names, dedupe before upgrading or the constraint creation fails.

Fresh dev SQLite needs no Alembic — `create_all()` on boot/seed builds the full current schema (incl. `clinic_id`). SQLite ALTERs run in Alembic batch mode (`render_as_batch`, set in `env.py`).

**Tests:** none in the repo. Verify behavior by driving the API (`/docs`, or curl against a running instance / container).

## Backend architecture

- **Config is centralized.** `app/core/config.py` is the ONLY module that reads env vars — everything imports the cached `settings` object. Swapping `DATABASE_URL` moves SQLite→Postgres with zero code changes (`app/core/database.py` sets SQLite-only connect args conditionally). In `ENVIRONMENT=production`, `settings` refuses to boot with the default `SECRET_KEY` (`model_post_init`).
- **Schema: `create_all()` for fresh DBs, Alembic for existing ones.** Fresh databases are still built by `Base.metadata.create_all()` (in `app/main.py` lifespan and `app/seed.py`) — that path always reflects the current models, including `clinic_id`. But `create_all()` never ALTERs an existing table, so schema changes to a live DB (e.g. Neon prod) go through **Alembic** (`backend/alembic/`, config in `alembic.ini`, URL pulled from `settings.DATABASE_URL` by `alembic/env.py`). Migration chain: `0001` = pre-tenancy baseline (a stamp target for DBs that already have those tables), `0002` = adds `clinics` + nullable `clinic_id` + backfills to a `default` clinic, `0003` = flips `clinic_id` to NOT NULL (all tenant tables except `users`) + per-clinic uniqueness. New model files MUST be imported in `app/models/__init__.py` or they won't register on `Base.metadata` (and Alembic autogenerate won't see them).
- **Multi-tenant (shared-schema row-level tenancy) — DONE (Session 2).** One API + one DB serve many clinics, fully isolated. `Clinic` (`app/models/clinic.py`, `slug` unique + `custom_domain`) is the tenant; every tenant-owned table (`Department`, `Doctor`, `DoctorAvailability`, `DoctorTimeOff`, `Appointment`, `ApiKey`, `VerificationCode`) carries a NOT NULL `clinic_id` FK. **`users.clinic_id` is nullable on purpose** — a `SUPERADMIN` is a global developer account with `clinic_id=NULL`; every PATIENT/ADMIN row has it set. Uniqueness is **per clinic**: `users(clinic_id,email)` / `(clinic_id,phone)` and `departments(clinic_id,name_ar|name_tr)` (so the same email/dept name can exist in different clinics); `api_keys.hashed_key` stays globally unique. Resolution deps (`app/dependencies.py`): `get_current_clinic` (X-Clinic slug header, fallback host/Origin → `custom_domain`; 400 if unresolved, 403 if inactive) for web/header endpoints, `get_current_clinic_optional` (login only — lets a headerless superadmin through), `get_api_key_clinic` (tenant = the clinic owning the API key, headers ignored) for `/api/v1/public/*`. **Every router query filters by the resolved clinic** — public reads scope by the X-Clinic header, JWT endpoints by `current_user.clinic_id` / `current_admin.clinic_id`, and `/public/*` by the key's clinic. `services.py` is unchanged: it's only ever called after the endpoint has verified the `doctor_id` belongs to the resolved clinic, and every row it reads is keyed to that doctor. **The cross-tenant leak is the failure mode that matters** — any new query on a tenant table MUST filter by `clinic_id`.
- **Superadmin (the developer).** `UserRole.SUPERADMIN`, guarded by `get_current_superadmin`. `/api/v1/superadmin/*` (`routers/superadmin.py`) is the ONLY place clinics are created/listed/deactivated and a clinic's first admin is created. Seeded from `SUPERADMIN_*` env vars with `clinic_id=NULL`. It logs in via `/auth/login` with **no** X-Clinic header (the optional-clinic dep falls back to a global superadmin lookup); it is NOT a clinic-admin, so it gets 403 from clinic-scoped endpoints.
- **Slots are computed, never stored.** `app/services.py:get_slots_for_doctor_on_date` generates bookable slots on the fly from a doctor's recurring weekly `DoctorAvailability` templates, minus `DoctorTimeOff`, minus non-cancelled `Appointment`s, minus past times. Editing a doctor's hours instantly affects all future dates. Booking calls `find_matching_slot` to re-validate the requested time server-side. Time arithmetic uses a fixed anchor date so a slot window crossing midnight terminates instead of looping.
- **Two auth models, both in `app/dependencies.py`:**
  - JWT Bearer (`get_current_user` / `get_current_admin` / `get_current_superadmin`) for the web portal. The role is always re-read from the DB row — the token's role claim is never trusted for authorization. Admin endpoints take the admin object as a param and scope every query to `admin.clinic_id`. `weekday` convention is Python's `Monday=0 … Sunday=6`.
  - API keys (`get_api_key`, `X-API-Key` header) for `/api/v1/public/*` — server-to-server bot/HIS integrations that book by phone number with no login. Keys are stored SHA-256-hashed; the raw key is shown once at creation. The key's `clinic_id` (via `get_api_key_clinic`) is the tenant for every `/public/*` query.
- **OTP flow** (`app/routers/auth.py`): password-reset ONLY — there is no signup verification. Registration creates the account immediately active (`is_verified=True`) and returns a JWT; there are no `/auth/verify/*` endpoints and no `verify.html` page. `VerificationCode` codes are bcrypt-hashed, expire, and are capped at `MAX_OTP_ATTEMPTS` wrong guesses via the shared `_consume_code` helper. `VerificationPurpose.ACCOUNT_VERIFY` still exists in the enum only so old DB rows deserialize — never issue it. Delivery is pluggable (`app/notifications.py`): `console` (logs the code — the zero-setup default) vs `smtp`/`twilio`, selected purely by env.
- **Concurrency:** booking endpoints lock the doctor row with `with_for_update()` to serialize concurrent bookings (real lock on Postgres/MySQL, no-op on SQLite). In `public.py`, patient find-or-create uses `flush()` not `commit()` so the lock is held until the appointment commits atomically.
- **One concern per file** under `models/`, `schemas/`, `routers/`. Emails are normalized to lowercase on register and on every lookup. Deleting a department with doctors, or a doctor with appointments, is rejected (409) to avoid FK orphans — deactivate (`is_active=False`) instead.

## Frontend architecture

- **Global objects, load order matters.** Scripts are plain `<script>` tags (no modules). Each page loads `config.js → auth.js → api.js → i18n.js → layout.js → [icons.js] → <page>.js`. These define globals: `CLINIC_CONFIG`, `Auth`, `Api`, `I18n`, `Layout`, `Icons`. Page logic is one IIFE per file (`home.js`, `booking.js`, `admin.js`, `my-appointments.js`) or inline in the auth HTML pages.
- **`config.js` is the only place the API URL lives** (`API_BASE_URL`) — edit it when deploying the backend elsewhere. Also holds `CLINIC_SLUG` (the tenant — one deployed frontend = one clinic; `api.js` sends it as the `X-Clinic` header on every request, so it must match a backend clinic `slug`) and clinic name/logo.
- **XSS: escape all API/user data going into `innerHTML`.** The codebase builds DOM via template-literal `innerHTML`. Every interpolation of server/user text MUST be wrapped in `esc()` (defined in `api.js`) — patient names, doctor names, department names, notes, key names, etc. `textContent` assignments and numeric IDs don't need it. i18n strings come from trusted static JSON.
- **i18n:** `I18n` (`i18n.js`) loads `assets/i18n/{ar,tr}.json`, sets `<html lang dir>` for RTL/LTR, translates `[data-i18n]` / `[data-i18n-placeholder]`, and fires a `clinic:langchange` event that pages listen to in order to re-render API-driven content in the new language. Add a language by copying a JSON file and adding a `.lang-switch` button.
- **Session:** `Auth` keeps JWT + user in `localStorage`. `Auth.requireAuth()` / `requireAdmin()` guard pages client-side (real enforcement is server-side). The `?next=` redirect after login is restricted to same-site `*.html` names.
- **Booking wizard** (`booking.js`): 4 steps (department → doctor → date/time → confirm). If a user hits "confirm" while logged out, the selection is stashed in `localStorage` (`clinic_booking_draft`) and restored after the login redirect.

## Deployment notes

- Frontend is hosted on **Cloudflare Pages** (build output dir = `frontend`, no build command).
- Backend runs on a **VPS via Portainer** (stack from this repo, compose path `backend/docker-compose.yml`), exposed over HTTPS through a **Cloudflare Tunnel** (`cloudflared` service → `clinic-api:8000`; host port mapping `8001:8000` is only for direct VPS access). Because frontend is HTTPS, the API must be HTTPS too (mixed-content otherwise).
- Current production hostnames: API at `https://clinic-api.dijivoo.com` (what `config.js` points to), frontend at `https://clinic.dijivoo.com` (allowed in `CORS_ORIGINS`). Data lives in **Neon** (managed Postgres), not on the VPS.
- After changing where either half is hosted: update `API_BASE_URL` in `config.js` AND `CORS_ORIGINS` (exact origin, no trailing slash) on the backend — a mismatch silently blocks every API call in the browser.
- `git push` uses HTTPS (SSH may be blocked on some networks); auth needs a GitHub PAT.

## Planned direction

`docs/session-prompts.md` is a six-session implementation roadmap (OTP-removal, multi-tenant SaaS core with Alembic, per-clinic theming, R2 media library, standalone bot service, chat widget). It describes **intended** architecture, not current state — each session is expected to update this file as it lands.
