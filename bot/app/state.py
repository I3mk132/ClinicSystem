"""
Lightweight in-memory conversation store with TTL.

The bot has NO access to the clinic DB - conversation state lives only here,
keyed by (tenant, conversation_id). Each state carries the chat history and the
patient identity (name + phone). The phone is the isolation boundary: every
appointment read/modify tool is executed with THIS phone, never one the model
supplies, so a conversation can never see another phone's data.

In-process only - for multi-replica production, swap this for Redis/SQLite
behind the same get/save/touch interface.
"""
import threading
import time as _time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.config import settings


@dataclass
class ConversationState:
    tenant: str
    conversation_id: str
    # patient identity, filled once known (from web client init or collected in chat)
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    # Gemini history: list of {"role": "user"|"model", "parts": [...]} dicts
    history: List[dict] = field(default_factory=list)
    # rate limiting: recent message unix timestamps
    recent_message_ts: List[float] = field(default_factory=list)
    updated_at: float = field(default_factory=_time.time)

    @property
    def has_identity(self) -> bool:
        return bool(self.patient_phone and self.patient_name)


class ConversationStore:
    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._data: Dict[Tuple[str, str], ConversationState] = {}
        self._lock = threading.Lock()

    def _evict_expired(self) -> None:
        cutoff = _time.time() - self._ttl
        stale = [k for k, v in self._data.items() if v.updated_at < cutoff]
        for k in stale:
            del self._data[k]

    def get_or_create(self, tenant: str, conversation_id: str) -> ConversationState:
        key = (tenant, conversation_id)
        with self._lock:
            self._evict_expired()
            state = self._data.get(key)
            if state is None:
                state = ConversationState(tenant=tenant, conversation_id=conversation_id)
                self._data[key] = state
            return state

    def save(self, state: ConversationState) -> None:
        state.updated_at = _time.time()
        # trim history to the last N turns to cap memory/token growth
        max_msgs = settings.MAX_HISTORY_TURNS * 2
        if len(state.history) > max_msgs:
            state.history = state.history[-max_msgs:]
        with self._lock:
            self._data[(state.tenant, state.conversation_id)] = state

    def allow_message(self, state: ConversationState) -> bool:
        """Per-conversation sliding-window rate limit."""
        now = _time.time()
        window_start = now - 60.0
        state.recent_message_ts = [t for t in state.recent_message_ts if t >= window_start]
        if len(state.recent_message_ts) >= settings.RATE_LIMIT_PER_MINUTE:
            return False
        state.recent_message_ts.append(now)
        return True


store = ConversationStore(settings.CONVERSATION_TTL_SECONDS)
