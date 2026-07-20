# ClinicSystem → Multi-Tenant SaaS: Session Prompts

Run these in order. Each prompt is self-contained and sized for one Claude Code session.
Each session should end with: CLAUDE.md updated to reflect the new architecture, so the next
session inherits correct context automatically.

**Dependency order:** 1 → 2 → 3 → 4 → 5 → 6. Session 1 is independent and can be done anytime.

---

## Session 1 — Remove signup OTP (small, independent) ✅ DONE (2026-07-19)

Landed: register sets `is_verified=True` and issues no code; `/auth/verify/*` endpoints,
`verify.html`, the unverified-banner in `layout.js`, and the `verify.*` i18n keys are all
removed. `VerificationPurpose.ACCOUNT_VERIFY` kept in the enum for old DB rows. Password
reset OTP untouched. `register.html` now honors the same safe `?next=` rule as login.

```
Read CLAUDE.md first.

Change the OTP/verification flow: remove the email/SMS verification step when a user
registers for the first time. New accounts should be immediately active (is_verified=True
on create, or remove the verified gate at login — check app/routers/auth.py and the User
model to see which applies).

Keep the existing VerificationCode OTP flow ONLY for:
- forgot password / reset password
- changing password while logged in (if an OTP step exists there)

Update the frontend auth pages accordingly: remove/skip the verify-code step after
registration, and make sure the register → login → booking flow works end to end.
Do not break the reset-password pages — they still use OTP.

Also check app/routers/public.py: patients auto-created by the public API must remain
consistent with whatever the new "no verification" rule is.

Verify by driving the API (register, login, forgot-password) against a running instance.
Update CLAUDE.md's OTP section when done.
```

---

## Session 2 — Multi-tenant core (foundation, everything depends on this) ✅ DONE (2026-07-19)

> Landed in two parts.
> **2a:** `Clinic` model (slug + custom_domain), `clinic_id` FK on all 8 tenant
> tables, Alembic introduced (`0001` baseline + `0002` tenancy), resolution deps
> (`get_current_clinic`, `get_api_key_clinic`), tenant-scoped seed (demo clinic).
> **2b:** every router + `services.py` now filters by the resolved clinic (public
> reads by X-Clinic header, JWT endpoints by the user/admin's `clinic_id`,
> `/public/*` by the API key's clinic); migration `0003` flips `clinic_id` to
> NOT NULL (except `users`, nullable for superadmin) + per-clinic uniqueness
> (email/phone/dept name); `SUPERADMIN` role + `/api/v1/superadmin/*` (create/
> list/deactivate clinics, create a clinic's first admin), seeded from
> `SUPERADMIN_*` env; frontend sends `CLINIC_SLUG` as `X-Clinic` on every request.
> Verified: two clinics fully isolated — cross-tenant admin/JWT/API-key access is
> 404/empty, same email registers independently per clinic, superadmin manages
> tenants without an X-Clinic header.

```
Read CLAUDE.md first.

Convert the backend to multi-tenant SaaS: many clinics share one database and one API
deployment. Use shared-schema row-level tenancy (a tenant_id column, NOT separate
databases or schemas).

Requirements:

1. New Clinic (tenant) model: id, slug (unique, URL-safe), name, custom_domain
   (nullable, unique), is_active, created_at. Register it in app/models/__init__.py.

2. Add clinic_id FK to every tenant-owned model: User, Department, Doctor,
   DoctorAvailability, DoctorTimeOff, Appointment, ApiKey, VerificationCode.
   Uniqueness that was global becomes per-tenant (e.g. user email unique per clinic,
   department name unique per clinic).

3. Introduce Alembic. The repo currently uses Base.metadata.create_all() with no
   migrations — that cannot alter existing tables. Add alembic, generate an initial
   migration for the current schema, then a migration for tenancy. Keep create_all()
   working for fresh dev SQLite. Document the migration workflow in CLAUDE.md.

4. Tenant resolution:
   - Public + web-portal endpoints: resolve tenant from an X-Clinic header carrying the
     slug (frontend will send it; slug lives in frontend config.js as CLINIC_SLUG),
     with fallback to resolving by request Origin/host against custom_domain.
   - API-key endpoints (/api/v1/public/*): the ApiKey row itself belongs to a clinic —
     resolve tenant from the key, ignore headers. A key must never read another
     clinic's data.
   - Make a get_current_clinic dependency in app/dependencies.py; every router uses it.
     Every query in routers/services must filter by clinic_id. Audit all of
     app/routers/* and app/services.py for missed filters — a cross-tenant leak is the
     failure mode that matters most here.

5. Roles: existing "admin" becomes clinic-admin (scoped to their clinic). Add a
   "superadmin" role (me, the developer) with endpoints under /api/v1/superadmin/* to
   create/list/deactivate clinics and create the first admin user for a clinic.
   Superadmin is created by seed from env vars.

6. Update app/seed.py: seed now creates a demo clinic + its admin + demo data, all
   tenant-scoped. SEED_DEMO_DATA behavior unchanged.

7. Frontend: add CLINIC_SLUG to config.js, send X-Clinic header on every request in
   api.js. No other frontend changes in this session.

Out of scope: theming, media, chatbot (later sessions).

Verify: create two clinics via superadmin endpoints, book appointments in both, prove
clinic A's admin/JWT/API-key can never see clinic B's doctors, patients, or
appointments. Update CLAUDE.md's architecture section thoroughly — later sessions
depend on it.
```

---

## Session 3 — Per-clinic theming + developer config presets ✅ DONE

Landed: `clinics.theme_preset` + `theme_overrides` (JSON) columns (migration `0004`);
developer presets in `backend/app/themes/*.json` (`default`, `modern`); `app/theme.py`
merge (`effective_theme`); no-auth `GET /api/v1/public/theme` (X-Clinic) in
`routers/theme.py:public_router`; admin `GET`/`PUT /api/v1/admin/theme`; superadmin
`GET /superadmin/presets` + `PATCH /superadmin/clinics/{id}/preset`; frontend `theme.js`
(cached CSS-variable apply, logo/name/text swap, `data-theme-text` nodes) loaded on every
page; admin **Theme** panel (colour pickers + per-language texts + logo, live preview).
Verified: two clinics render different colours/preset/logo/texts from one deployed frontend.

```
Read CLAUDE.md first. Requires the multi-tenant core (clinic model, X-Clinic
resolution) to already exist.

Add per-clinic theming and branding:

1. Backend: ClinicTheme storage per clinic (either a JSON column on Clinic or a
   ClinicTheme table). Admin-editable fields: primary/secondary/accent colors, logo
   URL, clinic display name (ar + tr), hero title/subtitle texts (ar + tr), contact
   info (phone, address ar + tr), footer text.

2. Developer-controlled presets: JSON preset files in backend/app/themes/ (e.g.
   default.json, modern.json) defining big decisions — font family/imports, full
   color palettes, border radius, layout density. Clinic model gets theme_preset
   (preset name). Presets are changeable only by me (files in repo + superadmin
   endpoint to switch a clinic's preset). Admin overrides layer on top of the preset:
   effective theme = preset merged with clinic overrides.

3. Public endpoint GET /api/v1/public/theme (resolved via X-Clinic, no auth) returning
   the merged effective theme.

4. Frontend: on every page load, fetch the theme before/while rendering, apply as CSS
   custom properties on :root (colors, fonts, radius), swap logo and text nodes.
   Cache it in localStorage to avoid flash of unstyled brand, refresh in background.
   Structure existing CSS so colors/fonts flow from CSS variables (refactor the
   stylesheet's hardcoded values into variables once).

5. Admin panel: new "Theme" section — color pickers, text inputs (per language), logo
   URL field (file upload comes next session), live preview if cheap to build.
   Escape everything with esc() as CLAUDE.md mandates.

Verify: two clinics show different colors/logo/texts from the same deployed frontend.
Update CLAUDE.md.
```

---

## Session 4 — Cloudflare R2 media library + homepage content sections ✅ DONE (2026-07-20)

Landed: R2 storage via `app/storage.py` (lazy boto3, S3v4 presigned PUT, `is_enabled()`
gate → 503 when unconfigured). Two tenant-owned tables + migration `0005`: `MediaAsset`
(kind logo/doctor_photo/equipment/gallery/section_image, unique clinic-prefixed
`object_key`, nullable `section_id`) and `ClinicSection` (kind gallery/equipment/team/
custom, bilingual title+body, `sort_order`, `is_active`). `routers/media.py`: admin media
presign/confirm/list/patch/delete + section CRUD/reorder (all scoped to `admin.clinic_id`),
no-auth `GET /public/sections` (X-Clinic). Isolation lives in the **server-generated,
clinic-prefixed key** — confirm/delete reject keys outside `clinics/{clinic_id}/`. Frontend:
`Api.uploadMedia` three-hop upload (presign → bare PUT to R2 → confirm), admin **Media &
Homepage** panel (library + section CRUD + reorder + assign-to-doctor + logo upload wired
into the Theme panel), homepage renders sections (`home.js` → `#clinic-sections`, bilingual,
lazy, `esc()`). R2 env vars in `docker-compose.yml`/`.env.example`; CLAUDE.md updated.
Verified (TestClient, 24/24): presign signs + clinic-prefixes, oversize→413, bad type→422,
confirm idempotent, public sections isolated per clinic, clinic B can't claim A's key / use
A's section / reorder A / see A's media, section delete detaches images, R2-off→503.

```
Read CLAUDE.md first. Requires multi-tenancy + theme sessions done.

Add image management backed by Cloudflare R2:

1. Backend R2 integration using boto3 S3-compatible API. New env vars in
   app/core/config.py only: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
   R2_BUCKET, R2_PUBLIC_BASE_URL. Upload flow: admin requests a presigned PUT URL
   from the backend (POST /api/v1/admin/media/presign — validates content-type and
   size, generates a tenant-scoped object key like clinics/{clinic_id}/{uuid}.webp),
   browser uploads directly to R2, then confirms to create a MediaAsset row
   (clinic_id, url, kind, alt texts ar/tr). Add delete endpoint (removes from R2 +
   DB). Every media object key MUST be prefixed with the clinic id.

2. MediaAsset kinds: logo, doctor_photo, equipment, gallery, section_image.
   Doctor model gets photo (MediaAsset FK or URL).

3. Homepage content sections: ClinicSection model (clinic_id, kind: gallery |
   equipment | team | custom, title ar/tr, body ar/tr, sort_order, is_active, linked
   media). Public endpoint returns active sections with images for the clinic.

4. Admin panel: "Media & Homepage" section — upload images (drag-drop or file input →
   presign → PUT → confirm), assign photos to doctors, create/reorder/edit homepage
   sections and attach images. Wire the Theme section's logo field to real upload now.

5. Frontend homepage: render the clinic's sections (photo grid for gallery/equipment,
   doctor cards with photos), bilingual, RTL-correct, lazy-loaded images, esc() on all
   text.

6. Add the R2 env vars to backend/docker-compose.yml (passed from stack env) and
   document R2 bucket + public-access setup in CLAUDE.md deployment notes.

Verify end to end: upload from admin panel appears on the public homepage; clinic A
cannot presign/delete into clinic B's prefix. Update CLAUDE.md.
```

---

## Session 5 — Channel-agnostic AI bot backend (Gemini 1.5 Flash) — ✅ DONE

**Landed:** standalone `bot/` FastAPI service (no `backend/app` import, no DB). Channel-agnostic `ConversationEngine` + `web` adapter (`POST /bot/v1/chat`), `X-Bot-Tenant` → clinic API key registry. Gemini 1.5 Flash manual function calling over 8 tools, each a thin public-API wrapper. Identity (name/phone) lives in conversation state and is injected server-side — appointment tools take no phone arg, so a conversation can never read another phone's data (verified). Safety rails: length cap (413), per-conversation rate limit, TTL state store, tool-result prompt-injection stripping. Backend gained `POST /public/appointments/{id}/reschedule` (API-key, clinic-scoped, frees the old slot). `clinic-bot` compose service added. Verified: 13/13 bot isolation/safety checks + 10/10 backend reschedule + cross-tenant checks. CLAUDE.md updated.

```
Read CLAUDE.md first. Requires multi-tenancy done. This session is backend only — the
web chat widget UI is the next session.

Build a standalone bot service that will power web chat now and WhatsApp/Telegram
later. Hard architectural rules:

- Lives in its own top-level directory bot/ as a separate FastAPI app with its own
  requirements.txt and Dockerfile. It must NOT import from backend/app or touch the
  database. Its ONLY access to clinic data is the existing public REST API
  (/api/v1/public/*) authenticated with X-API-Key — exactly how the future
  WhatsApp/Telegram bots will connect. Each clinic's bot instance is configured with
  that clinic's API key (generated in the admin panel, as today).

- Channel-agnostic core: a ConversationEngine that takes (channel, conversation_id,
  user_message) and returns reply text, with pluggable channel adapters. Implement
  the "web" adapter now (POST /bot/v1/chat with JSON in/out, conversation state
  keyed by a conversation_id the client holds); leave adapter interfaces ready for
  whatsapp/telegram. Conversation state in the bot's own lightweight store (SQLite
  or in-memory with TTL — bot has no access to the clinic DB).

- LLM: Gemini 1.5 Flash via the google-generativeai SDK, using function calling.
  GEMINI_API_KEY from env. Tools exposed to the model:
  list_departments, list_doctors, get_available_slots, book_appointment,
  list_my_appointments, cancel_appointment, reschedule_appointment.
  Each tool is a thin wrapper over a public API call.

- Identity & isolation (enforced in code, never trusted to the model): the patient is
  identified by phone number. If the web client initializes the chat with a logged-in
  user's identity, use it; otherwise the bot's first job is to collect name + phone
  conversationally and use the public API's find-or-create-by-phone booking flow.
  Every appointment-reading/modifying tool call is executed server-side with the
  phone number stored in the conversation state — the model can never pass an
  arbitrary phone number to see someone else's data. Extend backend/app/routers/
  public.py with the missing endpoints this requires (list appointments by phone,
  cancel, reschedule — API-key auth, clinic-scoped), since booking-only exists today.

- Behavior via system prompt: ONLY talks about this clinic — appointments,
  departments, doctors, hours, directions; politely refuses everything else. Very
  short answers (1–3 sentences). Warm, empathetic, listens to the patient. Replies
  in the patient's language (Arabic or Turkish, mirror whichever they use). Never
  invents medical advice.

- Safety rails outside the prompt: max message length, per-conversation rate limit,
  strip/refuse prompt-injection attempts in tool results, log conversations
  (without leaking them cross-tenant).

- Add the bot service to backend/docker-compose.yml (or its own compose file) with
  GEMINI_API_KEY and per-clinic API key config; document how a clinic's bot gets
  provisioned (admin creates API key → developer configures bot tenant entry).

Verify with curl against the running bot: full booking conversation, listing own
appointments, cancel, refusal of off-topic questions, and prove one conversation can
never read another phone number's appointments. Update CLAUDE.md with the bot
architecture.
```

---

## Session 6 — Web chat widget (frontend)

```
Read CLAUDE.md first. Requires the bot backend (Session 5) running.

Add a chat widget to the public frontend, matching the existing no-build vanilla-JS
architecture:

1. New chatbot.js (+ chatbot.css) loaded on public pages after the existing script
   chain. Floating action button in a screen corner (position must respect RTL:
   bottom-left in Arabic, bottom-right in Turkish — flip with the i18n direction).
   Opens a chat panel: header with clinic name/logo from the theme, scrollable
   message list, input row, typing indicator while awaiting the bot, timestamps.
   Design it polished — smooth open/close animation, mobile-friendly (full-height
   sheet on small screens), theme CSS variables for colors so it matches each
   clinic's branding.

2. Talks to the bot service's web endpoint. Bot service URL comes from config.js
   (BOT_BASE_URL) plus the clinic slug. Keep conversation_id + transcript in
   localStorage so the conversation survives reloads; add a "new conversation"
   reset button.

3. If the user is logged in (Auth from auth.js), initialize the conversation with
   their name/phone so the bot skips the identity questions. If not, the bot
   collects identity in-chat (already handled server-side).

4. Admin panel: a "Chatbot" toggle in settings (enabled/disabled per clinic, stored
   with the theme/clinic settings) — widget only renders when enabled.

5. i18n: all widget chrome strings added to ar.json and tr.json; re-render on
   clinic:langchange. esc() every message before inserting into innerHTML — bot and
   user text are both untrusted.

Verify in the browser: full booking conversation through the widget in Arabic and
Turkish, RTL layout correct, works logged-in and logged-out, disabled toggle hides
it. Update CLAUDE.md.
```

---

## Notes for you (the developer)

- **Why this order:** tenancy touches every table and every query — doing it first means
  theme/media/bot are built tenant-aware instead of retrofitted. OTP removal (Session 1)
  is isolated and can be done whenever.
- **Alembic in Session 2 is not optional** — production DB (Neon) already has data;
  `create_all()` can't add `clinic_id` columns to existing tables.
- **The bot never touches your DB.** It is a public-API client with an API key, so the
  WhatsApp/Telegram adapters later are just new thin adapters on the same
  ConversationEngine — no backend changes.
- **Session sizing:** 2 and 5 are the heavy ones. If Session 2 runs long, split it:
  (a) models + Alembic + tenant resolution, (b) query audit + superadmin + seed + frontend header.
