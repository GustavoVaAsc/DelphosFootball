"""Pure-logic tests for `harness.py`: request building, preflight exit, JSONL recording.

No server and no database: the preflight case targets an unused localhost port, and
recording is verified by reading the JSONL back.
"""

from __future__ import annotations

import json
import socket

import pytest
from harness import (
    HarnessConfig,
    HarnessError,
    build_request,
    build_row,
    parse_completion,
    preflight,
    record,
    server_root,
)

MESSAGES = [{"role": "user", "content": "hola"}]

CONFIG = HarnessConfig(
    base_url="http://127.0.0.1:9/v1",
    model="test-model",
    timeout_seconds=5.0,
    temperature=0.7,
    top_p=0.8,
    top_k=20,
    presence_penalty=0.0,
    enable_thinking=False,
    max_tokens=512,
)

VALID_PAYLOAD = {
    "model": "test-model",
    "choices": [{"message": {"content": "respuesta"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    "timings": {
        "prompt_n": 3,
        "predicted_n": 2,
        "prompt_per_second": 12.5,
        "predicted_per_second": 40.0,
    },
}


def test_build_request_carries_seed_and_sampling_params() -> None:
    body = build_request(MESSAGES, seed=101, config=CONFIG)
    assert body["seed"] == 101
    assert body["temperature"] == 0.7
    assert body["top_p"] == 0.8
    assert body["top_k"] == 20
    assert body["presence_penalty"] == 0.0
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["model"] == "test-model"
    assert body["messages"] == MESSAGES
    assert body["stream"] is False
    assert body["max_tokens"] == 512
    # Optional knobs stay out of the body unless asked for.
    assert "tools" not in body
    assert "response_format" not in body


def test_build_request_requires_an_explicit_seed() -> None:
    with pytest.raises(TypeError):
        build_request(MESSAGES, config=CONFIG)  # type: ignore[call-arg]


def test_build_request_overrides_reach_the_body() -> None:
    body = build_request(
        MESSAGES,
        seed=7,
        config=CONFIG,
        temperature=0.2,
        enable_thinking=True,
        tools=[{"type": "function", "function": {"name": "search_players"}}],
    )
    assert body["seed"] == 7
    assert body["temperature"] == 0.2
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    assert body["tools"][0]["function"]["name"] == "search_players"


def test_build_request_rejects_empty_messages() -> None:
    with pytest.raises(HarnessError):
        build_request([], seed=1, config=CONFIG)


def test_server_root_strips_the_v1_suffix() -> None:
    assert server_root("http://inference-chat:8080/v1") == "http://inference-chat:8080"
    assert server_root("http://inference-chat:8080/v1/") == "http://inference-chat:8080"
    assert server_root("http://inference-chat:8080") == "http://inference-chat:8080"


def _bound_idle_port() -> tuple[socket.socket, str]:
    """A port bound but never listening: connections are refused, and nobody can reuse it."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    return sock, f"http://127.0.0.1:{sock.getsockname()[1]}"


def test_preflight_unreachable_exits_with_a_clear_message(capsys: pytest.CaptureFixture) -> None:
    sock, url = _bound_idle_port()
    try:
        with pytest.raises(SystemExit) as excinfo:
            preflight(url)
    finally:
        sock.close()
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "preflight failed" in captured.err
    assert "unreachable" in captured.err
    assert url in captured.err
    assert "Traceback" not in captured.err


def test_parse_completion_valid_payload() -> None:
    result = parse_completion(VALID_PAYLOAD)
    assert result.content == "respuesta"
    assert result.model == "test-model"
    assert result.usage["prompt_tokens"] == 3
    assert result.timings["prompt_n"] == 3
    assert result.raw is VALID_PAYLOAD


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        {"choices": []},
        {"choices": [{"message": {"content": "   "}}]},
        {"choices": [{"message": {}}]},
        {"choices": ["not-a-choice"]},
    ],
    ids=["not-dict", "no-choices", "blank-content", "no-message", "bad-choice"],
)
def test_parse_completion_malformed_payloads_raise(payload: object) -> None:
    with pytest.raises(HarnessError) as excinfo:
        parse_completion(payload)
    assert str(excinfo.value)


def test_record_writes_one_parseable_row() -> None:
    request = build_request(MESSAGES, seed=101, config=CONFIG)
    result = parse_completion(VALID_PAYLOAD)
    row = build_row(request, result, experiment="unit_smoke", case_id="t1")
    assert row["seed"] == 101
    assert row["params"]["temperature"] == 0.7
    assert row["params"]["enable_thinking"] is False
    assert row["usage"]["total_tokens"] == 5
    assert row["timings"]["predicted_per_second"] == 40.0
    assert row["raw"] is VALID_PAYLOAD

    path = record("unit_smoke", row)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        written = json.loads(lines[0])
        assert written == row
    finally:
        path.unlink(missing_ok=True)


def test_record_rejects_path_traversal_in_experiment_name() -> None:
    with pytest.raises(HarnessError):
        record("../escape", {"x": 1})
