"""
Bot service FastAPI app.

Standalone: no import from backend/app, no DB. Tenant -> clinic API key comes
from config.BOT_TENANTS; the tenant is sent by the client as the `X-Bot-Tenant`
header (one deployed web widget = one clinic, mirroring the frontend's X-Clinic).
"""
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.web import WebAdapter, WebChatRequest, WebChatResponse
from app.config import settings
from app.engine import ConversationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("bot")

app = FastAPI(title="Clinic Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

_web_adapter = WebAdapter()


def resolve_tenant(x_bot_tenant: str = Header(..., alias="X-Bot-Tenant")) -> tuple[str, str]:
    """Map the tenant header to its clinic API key; 404 if unknown/unconfigured."""
    tenant = x_bot_tenant.strip()
    api_key = settings.tenants.get(tenant)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown bot tenant")
    return tenant, api_key


@app.get("/health")
def health():
    return {
        "status": "ok",
        "gemini": settings.gemini_enabled,
        "tenants": sorted(settings.tenants.keys()),
    }


@app.post("/bot/v1/chat", response_model=WebChatResponse)
async def web_chat(
    payload: WebChatRequest,
    tenant_key: tuple[str, str] = Depends(resolve_tenant),
):
    tenant, api_key = tenant_key

    if not settings.gemini_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot LLM not configured")

    # Safety rail: message length cap (checked in code, outside the model).
    if len(payload.message) > settings.MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Message too long (max {settings.MAX_MESSAGE_CHARS} chars)",
        )

    msg = _web_adapter.parse(payload)
    msg.tenant = tenant
    engine = ConversationEngine(tenant=tenant, api_key=api_key)
    reply = await _web_adapter.dispatch(engine, msg)
    return WebChatResponse(conversation_id=payload.conversation_id, reply=reply)
