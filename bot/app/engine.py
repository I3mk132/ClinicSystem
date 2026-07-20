"""
Channel-agnostic conversation engine.

`ConversationEngine.handle(...)` takes (tenant, channel, conversation_id,
user_message) plus an optional trusted identity, and returns reply text. It is
independent of HTTP/web/WhatsApp/Telegram - channel adapters (see adapters/) do
the transport translation and call this.

LLM: Gemini 1.5 Flash via google-generativeai, manual function calling. Tools
run server-side; identity (name/phone) is injected from conversation state, never
taken from the model (see tools.py).
"""
import asyncio
import logging
from datetime import date
from typing import Optional

import google.generativeai as genai

from app.clinic_api import ClinicApiClient
from app.config import settings
from app.prompt import SYSTEM_PROMPT
from app.safety import sanitize_tool_result
from app.state import ConversationState, store
from app.tools import GEMINI_TOOLS, execute_tool

logger = logging.getLogger("bot.engine")

_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True


def _proto_to_native(value):
    """Convert Gemini proto arg values (MapComposite/RepeatedComposite) to plain Python."""
    if hasattr(value, "items"):
        return {k: _proto_to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)) or (hasattr(value, "__iter__") and not isinstance(value, (str, bytes))):
        return [_proto_to_native(v) for v in value]
    return value


def _build_model() -> "genai.GenerativeModel":
    system_instruction = f"{SYSTEM_PROMPT}\n\nToday's date is {date.today().isoformat()}."
    return genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=system_instruction,
        tools=[GEMINI_TOOLS],
    )


def _function_calls(response):
    calls = []
    try:
        parts = response.candidates[0].content.parts
    except (IndexError, AttributeError):
        return calls
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            calls.append(fc)
    return calls


def _safe_text(response) -> str:
    try:
        return response.text.strip()
    except Exception:
        return ""


class ConversationEngine:
    def __init__(self, tenant: str, api_key: str):
        self.tenant = tenant
        self.client = ClinicApiClient(api_key)

    async def handle(
        self,
        channel: str,
        conversation_id: str,
        user_message: str,
        init_identity: Optional[dict] = None,
    ) -> str:
        _ensure_configured()
        state: ConversationState = store.get_or_create(self.tenant, conversation_id)

        # Trusted identity from a logged-in web client - set once, never overwritten
        # by later messages, and never taken from the model.
        if init_identity and not state.has_identity:
            name = str(init_identity.get("full_name", "")).strip()
            phone = str(init_identity.get("phone", "")).strip()
            if len(name) >= 2 and len(phone) >= 5:
                state.patient_name = name
                state.patient_phone = phone

        if not store.allow_message(state):
            return _rate_limited_message(state)

        model = _build_model()
        chat = model.start_chat(history=state.history)

        try:
            response = await asyncio.to_thread(chat.send_message, user_message)
            for _ in range(settings.MAX_TOOL_ITERATIONS):
                calls = _function_calls(response)
                if not calls:
                    break
                parts = []
                for fc in calls:
                    args = _proto_to_native(fc.args) if fc.args else {}
                    result = sanitize_tool_result(await execute_tool(fc.name, args, self.client, state))
                    logger.info(
                        "tool_call tenant=%s conv=%s channel=%s tool=%s ok=%s",
                        self.tenant, conversation_id, channel, fc.name, "error" not in result,
                    )
                    parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(name=fc.name, response=result)
                        )
                    )
                response = await asyncio.to_thread(
                    chat.send_message, genai.protos.Content(role="user", parts=parts)
                )
            reply = _safe_text(response) or _fallback_message(state)
        except Exception:
            logger.exception("engine failure tenant=%s conv=%s", self.tenant, conversation_id)
            reply = _error_message(state)
        finally:
            # Persist the model-managed history (in-memory proto objects).
            state.history = list(chat.history)
            store.save(state)

        return reply


# Minimal bilingual canned fallbacks (used only when the model can't reply).
def _rate_limited_message(state: ConversationState) -> str:
    return "أرسلت رسائل كثيرة بسرعة. أمهلني قليلاً ثم حاول مجدداً." \
        if _is_arabic(state) else "Çok fazla mesaj gönderdiniz. Lütfen biraz bekleyip tekrar deneyin."


def _fallback_message(state: ConversationState) -> str:
    return "عذراً، لم أفهم تماماً. كيف أساعدك بخصوص مواعيد العيادة؟" \
        if _is_arabic(state) else "Üzgünüm, tam anlayamadım. Randevu konusunda nasıl yardımcı olabilirim?"


def _error_message(state: ConversationState) -> str:
    return "حدث خطأ مؤقت. من فضلك حاول مرة أخرى بعد قليل." \
        if _is_arabic(state) else "Geçici bir hata oluştu. Lütfen birazdan tekrar deneyin."


def _is_arabic(state: ConversationState) -> bool:
    """Heuristic: was the last user message Arabic? Default Turkish (LTR clinic)."""
    for content in reversed(state.history):
        role = getattr(content, "role", None)
        if role == "user":
            for part in getattr(content, "parts", []):
                text = getattr(part, "text", "") or ""
                if text:
                    return any("؀" <= ch <= "ۿ" for ch in text)
    return False
