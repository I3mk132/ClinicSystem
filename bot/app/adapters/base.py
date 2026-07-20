"""
Channel adapter interface.

An adapter translates a specific transport (web JSON now; WhatsApp/Telegram
webhooks later) into a call to the channel-agnostic ConversationEngine and
formats the reply back. Keeping this boundary explicit is the whole point of the
"channel-agnostic core": adding WhatsApp = adding a new adapter, no engine change.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.engine import ConversationEngine


class InboundMessage:
    """Normalized inbound message every adapter produces."""

    def __init__(
        self,
        tenant: str,
        conversation_id: str,
        text: str,
        init_identity: Optional[dict] = None,
    ):
        self.tenant = tenant
        self.conversation_id = conversation_id
        self.text = text
        self.init_identity = init_identity


class ChannelAdapter(ABC):
    channel: str

    @abstractmethod
    def parse(self, raw: object) -> InboundMessage:
        """Transport payload -> normalized InboundMessage."""
        ...

    async def dispatch(self, engine: ConversationEngine, msg: InboundMessage) -> str:
        return await engine.handle(
            channel=self.channel,
            conversation_id=msg.conversation_id,
            user_message=msg.text,
            init_identity=msg.init_identity,
        )
