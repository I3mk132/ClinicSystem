# Clinic Bot

Standalone, channel-agnostic AI appointment assistant for the clinic system.

- **No coupling to the backend.** It never imports `backend/app` and never touches
  the DB. Its only access to clinic data is the public REST API
  (`/api/v1/public/*`) authenticated per clinic with `X-API-Key` — the exact path
  a future WhatsApp/Telegram bot will use.
- **Channel-agnostic core.** `ConversationEngine.handle(channel, conversation_id,
  message)` returns reply text; transport lives in `app/adapters/`. The `web`
  adapter (`POST /bot/v1/chat`) is implemented now; whatsapp/telegram slot in as
  new adapters with no engine change.
- **LLM.** Gemini 1.5 Flash via `google-generativeai`, manual function calling.
  Tools: `list_departments`, `list_doctors`, `get_available_slots`,
  `book_appointment`, `list_my_appointments`, `cancel_appointment`,
  `reschedule_appointment` — each a thin wrapper over a public API call.
- **Identity & isolation.** The patient is identified by phone number, stored in
  conversation state. Tools that read/modify appointments take **no** phone
  argument — the executor injects the state's phone, so the model can never reach
  another patient's data. A logged-in web client may pass a trusted identity at
  init; otherwise the bot collects name + phone conversationally.

## Run (dev)

```bash
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # set GEMINI_API_KEY and BOT_TENANTS
uvicorn app.main:app --reload --port 9000
```

`GET /health` reports whether Gemini is configured and which tenants are known.

## Provisioning a clinic's bot

1. In the clinic **admin panel**, create an **API key** (shown once).
2. Add a `tenant=key` entry to `BOT_TENANTS`, e.g.
   `BOT_TENANTS=default=ck_live_abc123`. The `tenant` string is what the web
   widget sends in the `X-Bot-Tenant` header (one deployed widget = one clinic).
3. Point `CLINIC_API_BASE_URL` at the backend's public API and set
   `CORS_ORIGINS` to the widget's origin.

## Chat request

```
POST /bot/v1/chat
Headers: X-Bot-Tenant: default
{
  "conversation_id": "a-client-generated-uuid",
  "message": "أريد حجز موعد",
  "identity": { "full_name": "Ali", "phone": "+905551112233" }   // optional
}
→ { "conversation_id": "...", "reply": "..." }
```
