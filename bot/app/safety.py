"""
Safety rails enforced in CODE, outside the model.

- Message length cap (config MAX_MESSAGE_CHARS) - checked at the adapter.
- Per-conversation rate limit - in state.ConversationStore.allow_message.
- Tool-result sanitization: clinic API data is echoed back into the model as
  tool results. Neutralize any prompt-injection strings that might sit in
  free-text fields (e.g. a doctor bio or a patient note) so they can't hijack
  the model. We do NOT trust the model with identity regardless, so this is
  defense in depth.
"""
import re
from typing import Any

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(system|above|previous)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
]

_MAX_FIELD_CHARS = 2000


def _clean_str(s: str) -> str:
    for pat in _INJECTION_PATTERNS:
        s = pat.sub("[filtered]", s)
    if len(s) > _MAX_FIELD_CHARS:
        s = s[:_MAX_FIELD_CHARS] + "…"
    return s


def sanitize_tool_result(value: Any) -> Any:
    """Recursively strip injection markers from any string in a tool result."""
    if isinstance(value, str):
        return _clean_str(value)
    if isinstance(value, dict):
        return {k: sanitize_tool_result(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_tool_result(v) for v in value]
    return value
