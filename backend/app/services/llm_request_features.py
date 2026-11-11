"""Request features a model refuses, learned from its own 400 and dropped on retry.

Providers retire request features per model: current Anthropic models answer 400
"`temperature` is deprecated for this model." (same for `top_p`) and "This model does
not support assistant message prefill." where older ones accepted both. A static
model-name table goes stale with every release, so the refusal itself is the source:
the first 400 naming a feature teaches the registry, the request is resent without it,
and every later request to that (provider, model) in this process omits it up front.
A refusal naming its successor ("Use 'max_completion_tokens' instead.") moves the value
to that name instead of dropping it.

A dropped prefill is emulated on the reply (:func:`continue_after_prefill`), so callers
that parse "the text after the prefill" keep seeing that shape.
"""

import re
import threading
from dataclasses import dataclass

#: Feature name used for a trailing assistant message (response prefill).
PREFILL = "assistant_prefill"

# Verbatim live 400s: "`temperature` is deprecated for this model." (Anthropic);
# "Unsupported parameter: 'top_p' is not supported with this model." and
# "Unsupported value: 'temperature' does not support 0.3 with this model." (OpenAI).
_PARAM_REFUSAL = re.compile(
    r"[`'\"](?P<param>[a-z_]+)[`'\"] "
    r"(?:is (?:deprecated|not supported|unsupported)|does not support)",
    re.I,
)
# "... Use 'max_completion_tokens' instead." (OpenAI, refusing `max_tokens`).
_SUCCESSOR = re.compile(r"Use [`'\"](?P<param>[a-z_]+)[`'\"] instead", re.I)
_PREFILL_REFUSAL = re.compile(r"does not support assistant message prefill", re.I)

#: (provider, model) -> refused feature -> the name its value moves to (None: dropped).
_learned: dict[tuple[str, str], dict[str, str | None]] = {}
_lock = threading.Lock()


@dataclass(frozen=True)
class Stripped:
    """What was removed from one payload: feature names and the prefill text, if any."""

    features: tuple[str, ...] = ()
    prefill: str | None = None


def _has(payload: dict, feature: str) -> bool:
    if feature == PREFILL:
        messages = payload.get("messages") or []
        return bool(messages) and messages[-1].get("role") == "assistant"
    return feature in payload


def _strip(payload: dict, feature: str, successor: str | None) -> str | None:
    """Remove ``feature`` from ``payload`` in place (its value moved to ``successor``
    when given); return the prefill text it held."""
    if not _has(payload, feature):
        return None
    if feature == PREFILL:
        return str(payload["messages"].pop().get("content", ""))
    value = payload.pop(feature)
    if successor:
        payload.setdefault(successor, value)
    return None


def strip_learned(key: tuple[str, str], payload: dict) -> Stripped:
    """Drop from ``payload`` every feature learned as refused for ``key`` (provider, model)."""
    with _lock:
        refused = sorted(_learned.get(key, {}).items())
    prefill = None
    for feature, successor in refused:
        prefill = _strip(payload, feature, successor) or prefill
    return Stripped(tuple(feature for feature, _ in refused), prefill)


def learn_refusal(key: tuple[str, str], payload: dict, status: int, body: str) -> str | None:
    """Record the feature a 400 ``body`` refuses, if ``payload`` carries it; return its name.

    ``None``: not a feature refusal this module knows, or one naming a feature the
    payload does not hold — the caller raises the error as before.
    """
    if status != 400:
        return None
    successor = None
    if _PREFILL_REFUSAL.search(body):
        feature = PREFILL
    elif match := _PARAM_REFUSAL.search(body):
        feature = match["param"]
        if hint := _SUCCESSOR.search(body):
            successor = hint["param"]
    else:
        return None
    if not _has(payload, feature) or successor == feature:
        return None
    with _lock:
        _learned.setdefault(key, {})[feature] = successor
    return feature


def continue_after_prefill(content: str, prefill: str | None) -> str:
    """Shape a reply produced WITHOUT ``prefill`` as the continuation of it.

    A prefilled model emits only what follows the prefill (``{`` -> ``"a": 1}``). The
    same model unprefilled usually opens with the prefill itself, possibly inside a code
    fence: the text up to and including its first occurrence is dropped, with the
    closing fence when one was opened. A reply not containing it is returned unchanged.
    """
    marker = (prefill or "").strip()
    if not marker:
        return content
    index = content.find(marker)
    if index < 0:
        return content
    head, tail = content[:index], content[index + len(marker) :]
    if "```" in head:
        tail = tail.rstrip()
        if tail.endswith("```"):
            tail = tail[:-3].rstrip()
    return tail


def reset() -> None:
    """Forget everything learned (tests)."""
    with _lock:
        _learned.clear()
