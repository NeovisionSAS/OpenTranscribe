"""Refused request features are learned from the provider's 400 and dropped on retry.

Bodies are the verbatim 400 messages the live APIs returned: Anthropic for
claude-opus-5-5, OpenAI for gpt-5.
"""

import json

import pytest

from app.services import llm_request_features as features
from app.services.llm_service import LLMConfig
from app.services.llm_service import LLMProvider
from app.services.llm_service import LLMService

ANTHROPIC = "anthropic"
TEMPERATURE_400 = '{"error":{"message":"`temperature` is deprecated for this model."}}'
TOP_P_400 = '{"error":{"message":"`top_p` is deprecated for this model."}}'
PREFILL_400 = (
    '{"error":{"message":"This model does not support assistant message prefill. '
    'The conversation must end with a user message."}}'
)
OPENAI_VALUE_400 = (
    "Unsupported value: 'temperature' does not support 0.3 with this model. "
    "Only the default (1) value is supported."
)
OPENAI_PARAM_400 = "Unsupported parameter: 'top_p' is not supported with this model."
OPENAI_RENAMED_400 = (
    "Unsupported parameter: 'max_tokens' is not supported with this model. "
    "Use 'max_completion_tokens' instead."
)
OTHER_400 = '{"error":{"message":"max_tokens: 99999999 > 64000"}}'


def _payload(model: str) -> dict:
    return {
        "model": model,
        "max_tokens": 10,
        "temperature": 0.1,
        "top_p": 0.9,
        "messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "{"}],
    }


@pytest.fixture(autouse=True)
def _fresh_registry():
    features.reset()
    yield
    features.reset()


@pytest.mark.parametrize(
    ("model", "status", "body", "learned"),
    [
        ("claude-opus-5-5", 400, TEMPERATURE_400, "temperature"),
        ("claude-sonnet-5-5", 400, TOP_P_400, "top_p"),
        ("claude-haiku-5-5", 400, PREFILL_400, features.PREFILL),
        ("gpt-5", 400, OPENAI_VALUE_400, "temperature"),
        ("gpt-5", 400, OPENAI_PARAM_400, "top_p"),
        ("claude-opus-5-5", 400, OTHER_400, None),  # unrelated 400 stays an error
        ("claude-opus-5-5", 500, TEMPERATURE_400, None),  # only a 400 teaches
    ],
)
def test_learn_then_strip(model, status, body, learned):
    key = (ANTHROPIC, model)
    payload = _payload(model)
    assert features.learn_refusal(key, payload, status, body) == learned

    fresh = _payload(model)
    stripped = features.strip_learned(key, fresh)
    if learned is None:
        assert fresh == _payload(model) and stripped.features == ()
        return
    assert stripped.features == (learned,)
    if learned == features.PREFILL:
        assert fresh["messages"] == [{"role": "user", "content": "q"}]
        assert stripped.prefill == "{"
    else:
        assert learned not in fresh


def test_refusal_naming_a_successor_moves_the_value():
    key = ("openai", "gpt-5")
    assert features.learn_refusal(key, _payload("gpt-5"), 400, OPENAI_RENAMED_400) == "max_tokens"
    fresh = _payload("gpt-5")
    features.strip_learned(key, fresh)
    assert "max_tokens" not in fresh and fresh["max_completion_tokens"] == 10


def test_old_model_untouched_by_new_model_refusal():
    features.learn_refusal((ANTHROPIC, "claude-opus-5-5"), _payload("x"), 400, TEMPERATURE_400)
    old = _payload("claude-opus-4-5-20251101")
    assert features.strip_learned((ANTHROPIC, "claude-opus-4-5-20251101"), old).features == ()
    assert old["temperature"] == 0.1


def test_refusal_of_absent_feature_is_not_learned():
    payload = _payload("m")
    del payload["temperature"]
    assert features.learn_refusal((ANTHROPIC, "m"), payload, 400, TEMPERATURE_400) is None


@pytest.mark.parametrize(
    ("reply", "prefill", "expected"),
    [
        ('{"a": 1}', "{", '"a": 1}'),
        ('```json\n{"a": 1}\n```', "{", '"a": 1}'),
        ('Here it is: {"a": 1}', "{", '"a": 1}'),
        ("no brace", "{", "no brace"),
        ('{"a": 1}', None, '{"a": 1}'),
        (
            "<thinking>\nx</thinking><answer>{}</answer>",
            "<thinking>\n",
            "\nx</thinking><answer>{}</answer>",
        ),
    ],
)
def test_continue_after_prefill(reply, prefill, expected):
    assert features.continue_after_prefill(reply, prefill) == expected


class _Reply:
    def __init__(self, status: int, text: str):
        self.status_code, self.text = status, text

    def json(self):
        return json.loads(self.text)


def _anthropic_that_refuses(refuses_new_features: bool):
    """Fake transport: a current model refuses temperature + prefill, an old one accepts."""
    sent: list[dict] = []

    def post(self, url, payload, headers, timeout):
        sent.append(payload)
        if refuses_new_features and "temperature" in payload:
            return _Reply(400, TEMPERATURE_400)
        if refuses_new_features and payload["messages"][-1]["role"] == "assistant":
            return _Reply(400, PREFILL_400)
        text = '"a": 1}' if payload["messages"][-1]["role"] == "assistant" else '{"a": 1}'
        # Current models open with an empty `thinking` block; the answer is the `text` one.
        blocks = [{"type": "thinking", "thinking": ""}] if refuses_new_features else []
        return _Reply(200, json.dumps({"content": [*blocks, {"type": "text", "text": text}]}))

    return post, sent


@pytest.mark.parametrize(
    ("model", "refuses", "first_call_posts"),
    [("claude-opus-5-5", True, 3), ("claude-opus-4-5-20251101", False, 1)],
)
def test_service_resends_without_refused_features(monkeypatch, model, refuses, first_call_posts):
    post, sent = _anthropic_that_refuses(refuses)
    monkeypatch.setattr(LLMService, "_post_llm", post)
    service = LLMService(LLMConfig(provider=LLMProvider.ANTHROPIC, model=model, api_key="k"))
    messages = [{"role": "user", "content": "q"}]

    for posts_so_far in (first_call_posts, first_call_posts + 1):  # 2nd call: learned up front
        payload = service._prepare_payload(messages, temperature=0.1, prefill_json=True)
        body = service._send_llm_request("https://api.anthropic.com/v1/messages", payload, {}, 5)
        assert len(sent) == posts_so_far
        # Prefilled or not, the caller reads the continuation after "{".
        assert service._extract_claude_response(body)[0] == '"a": 1}'
    assert ("temperature" in sent[-1]) is not refuses
