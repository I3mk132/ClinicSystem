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

**Tests:** none in the repo. Verify behavior by driving the API (`/docs`, or curl against a running instance / container).

## Backend architecture

- **Config is centralized.** `app/core/config.py` is the ONLY module that reads env vars — everything imports the cached `settings` object. Swapping `DATABASE_URL` moves SQLite→Postgres with zero code changes (`app/core/database.py` sets SQLite-only connect args conditionally). In `ENVIRONMENT=production`, `settings` refuses to boot with the default `SECRET_KEY` (`model_post_init`).
- **Schema creation, not migrations.** Tables are created via `Base.metadata.create_all()` in the `lifespan` handler (`app/main.py`) and in `app/seed.py`. There is no Alembic — a model change to an existing table won't apply to an existing DB. New model files MUST be imported in `app/models/__init__.py` or they won't register on `Base.metadata`.
- **Slots are computed, never stored.** `app/services.py:get_slots_for_doctor_on_date` generates bookable slots on the fly from a doctor's recurring weekly `DoctorAvailability` templates, minus `DoctorTimeOff`, minus non-cancelled `Appointment`s, minus past times. Editing a doctor's hours instantly affects all future dates. Booking calls `find_matching_slot` to re-validate the requested time server-side. Time arithmetic uses a fixed anchor date so a slot window crossing midnight terminates instead of looping.
- **Two auth models, both in `app/dependencies.py`:**
  - JWT Bearer (`get_current_user` / `get_current_admin`) for the web portal. The role is always re-read from the DB row — the token's role claim is never trusted for authorization. `weekday` convention is Python's `Monday=0 … Sunday=6`.
  - API keys (`get_api_key`, `X-API-Key` header) for `/api/v1/public/*` — server-to-server bot/HIS integrations that book by phone number with no login. Keys are stored SHA-256-hashed; the raw key is shown once at creation.
- **OTP flow** (`app/routers/auth.py`): password-reset ONLY — there is no signup verification. Registration creates the account immediately active (`is_verified=True`) and returns a JWT; there are no `/auth/verify/*` endpoints and no `verify.html` page. `VerificationCode` codes are bcrypt-hashed, expire, and are capped at `MAX_OTP_ATTEMPTS` wrong guesses via the shared `_consume_code` helper. `VerificationPurpose.ACCOUNT_VERIFY` still exists in the enum only so old DB rows deserialize — never issue it. Delivery is pluggable (`app/notifications.py`): `console` (logs the code — the zero-setup default) vs `smtp`/`twilio`, selected purely by env.
- **Concurrency:** booking endpoints lock the doctor row with `with_for_update()` to serialize concurrent bookings (real lock on Postgres/MySQL, no-op on SQLite). In `public.py`, patient find-or-create uses `flush()` not `commit()` so the lock is held until the appointment commits atomically.
- **One concern per file** under `models/`, `schemas/`, `routers/`. Emails are normalized to lowercase on register and on every lookup. Deleting a department with doctors, or a doctor with appointments, is rejected (409) to avoid FK orphans — deactivate (`is_active=False`) instead.

## Frontend architecture

- **Global objects, load order matters.** Scripts are plain `<script>` tags (no modules). Each page loads `config.js → auth.js → api.js → i18n.js → layout.js → [icons.js] → <page>.js`. These define globals: `CLINIC_CONFIG`, `Auth`, `Api`, `I18n`, `Layout`, `Icons`. Page logic is one IIFE per file (`home.js`, `booking.js`, `admin.js`, `my-appointments.js`) or inline in the auth HTML pages.
- **`config.js` is the only place the API URL lives** (`API_BASE_URL`) — edit it when deploying the backend elsewhere. Also holds clinic name/logo.
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
