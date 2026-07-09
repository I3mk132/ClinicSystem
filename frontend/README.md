# Clinic Booking System — Frontend (static HTML/CSS/JS)

Plain HTML/CSS/JavaScript — **no build step, no framework, no bundler.**
It only talks to the backend over the REST API (see `assets/js/config.js`),
so it is completely decoupled from it: you can redeploy the frontend
anywhere (or replace it with a mobile app) without touching the backend.

## Running it locally

Any static file server works. For example:

```bash
cd frontend
python3 -m http.server 5500
# open http://127.0.0.1:5500
```

Or use the VS Code "Live Server" extension, or `npx serve`.

Make sure the backend is running too (see `../backend/README.md`) and that
its CORS_ORIGINS in `.env` includes the origin you're serving the frontend
from (`http://127.0.0.1:5500` by default — already included).

## Project layout

```
frontend/
  index.html              # landing page (hero, departments)
  login.html / register.html
  forgot-password.html    # request reset code -> confirm code + new password
  verify.html             # confirm the OTP sent after registration
  booking.html            # 4-step booking wizard
  my-appointments.html    # patient's own bookings
  admin.html              # admin dashboard (tabs, incl. Integrations/API keys)
  assets/
    css/
      style.css           # design tokens + all reusable components
      animations.css      # scroll-reveal & motion utilities
    js/
      config.js           # <-- API base URL + clinic name (edit this first)
      api.js               # fetch() wrapper (auth header, error handling)
      auth.js               # session (JWT) storage & guards
      i18n.js               # language engine (ar/tr, RTL/LTR)
      layout.js             # shared navbar/footer/toasts/modals/verify-banner
      icons.js               # inline SVG icon set for departments
      home.js / booking.js / my-appointments.js / admin.js   # one file per page
    i18n/
      ar.json / tr.json    # every UI string, add a new language by copying one
    images/                 # put your logo / photos here
```

Each HTML page only loads the JS files it actually needs, so it's easy to
add a new page: copy the `<head>`/navbar/footer boilerplate from an
existing page and write a new `assets/js/your-page.js`.

## Customizing for your clinic

| What | Where |
|---|---|
| Clinic name (AR/TR) | `assets/js/config.js` → `CLINIC_NAME` |
| Logo | `assets/js/config.js` → `CLINIC_LOGO_URL`, or replace the inline SVG mark in `layout.js` (`_logoSvg`) |
| Colors / fonts / spacing | CSS variables at the top of `assets/css/style.css` (`:root { ... }`) |
| Backend URL | `assets/js/config.js` → `API_BASE_URL` |
| UI text | `assets/i18n/ar.json`, `assets/i18n/tr.json` |
| Departments, doctors, photos, working hours | done live from the **Admin** page — no code changes needed |

## Adding a third language

1. Copy `assets/i18n/ar.json` to e.g. `assets/i18n/en.json` and translate
   every value (keep the keys identical).
2. Add a button to the `.lang-switch` markup in `layout.js`
   (`<button data-lang="en">EN</button>`).
3. If the new language is right-to-left, add it to the `dir` check in
   `i18n.js` (`applyDirection`); otherwise it defaults to LTR.

## Why plain JS instead of a framework?

Kept deliberately framework-free and dependency-free so it:
- loads fast on low-end devices/slow connections (a real concern for a
  clinic's patient base),
- has zero build tooling to maintain,
- is trivial to reason about page-by-page.

The backend is a clean, versioned REST API (`/api/v1/...`), so nothing
here stops you from later adding a React/Flutter/native mobile app that
talks to the exact same endpoints alongside (or instead of) this site.

## Account verification & forgot password

`register.html` lets the person choose whether their verification codes
go to their **email** or **phone** (`contact_method`). After signup they
land on `verify.html` to enter the code; a dismissible banner
(`Layout._mountBanner` in `layout.js`) reminds unverified users on every
page until they do. `login.html` links to `forgot-password.html`, a
two-step flow (request code → enter code + new password) that talks to
`POST /auth/password/forgot` and `POST /auth/password/reset`.

In development, codes are printed to the **backend's terminal** (no email
account or SMS provider needed to test) — see `backend/README.md` for how
to switch to real SMTP/Twilio delivery.

## Integrations (public API / bots)

Admin → **Integrations** tab lets you create/revoke API keys used by
external systems (a WhatsApp or Telegram bot, your main hospital system,
...) to book/list/cancel appointments without a user login — see
`backend/README.md` → "Public API for integrations" for the endpoints.
