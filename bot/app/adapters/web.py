"""Web chat adapter - JSON in / JSON out over HTTP (this session's channel)."""
from typing import Optional

from pydantic import BaseModel, Field

from app.adapters.base import ChannelAdapter, InboundMessage


class WebIdentity(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=5, max_length=30)


class WebChatRequest(BaseModel):
    # The client holds this and sends it every turn to continue the conversation.
    conversation_id: str = Field(min_length=8, max_length=128)
    message: str = Field(min_length=1)
    # Optional trusted identity when the web user is logged in.
    identity: Optional[WebIdentity] = None


class WebChatResponse(BaseModel):
    conversation_id: str
    reply: str


class WebAdapter(ChannelAdapter):
    channel = "web"

    def parse(self, raw: WebChatRequest) -> InboundMessage:
        identity = raw.identity.model_dump() if raw.identity else None
        return InboundMessage(
            tenant="",  # filled by the route from the resolved tenant
            conversation_id=raw.conversation_id,
            text=raw.message,
            init_identity=identity,
        )
