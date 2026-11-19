"""Consistency tests for the deployment files (docker-compose.yml, .env.example).

Input: the compose file and the environment template at the repository root.
Output: assertions on the rendered service environment.
Responsibility: keeps the model id the backend sends identical to the model id
the inference server serves, so a request can never fail to resolve its model.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
BACKEND_ENV_EXAMPLE = REPO_ROOT / "backend" / ".env.example"
ARCHITECTURE = REPO_ROOT / "docs/ARCHITECTURE.md"

DEFAULT_MODEL_ID = "qwen/qwen3.5-9b"
DEFAULT_MODEL_PATH = "/models/Qwen3.5-9B-Q5_K_M.gguf"
DEFAULT_PUBLISH_IP = "127.0.0.1"
DEFAULT_PUBLISH_PORT = "8081"
INFERENCE_CONTAINER_PORT = "8080"
PROMPT_VERSION_KEY = "DELPHOS_LLM_REPORT_PROMPT_VERSION"
PROMPT_VERSION_DEFAULT = "v2-t0.7-p0.8-k20"

_PUBLISH_ENTRY = re.compile(
    r"\$\{(?P<ip_variable>[^:]+):-(?P<ip_default>[^}]*)\}"
    r":\$\{(?P<port_variable>[^:]+):-(?P<port_default>[^}]*)\}"
    r":(?P<container_port>.+)"
)


def _service_environment(service: str) -> dict[str, str]:
    """Return the environment mapping of one service from the compose file."""
    lines = COMPOSE_FILE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  {service}:")), None)
    assert start is not None, f"service {service} not found in {COMPOSE_FILE}"
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line)
    try:
        env_at = next(i for i, line in enumerate(block) if line.strip() == "environment:")
    except StopIteration:  # pragma: no cover - defensive
        raise AssertionError(f"service {service} has no environment block") from None
    environment: dict[str, str] = {}
    for line in block[env_at + 1 :]:
        if not line.strip():
            continue
        if not line.startswith("      "):
            break
        key, _, value = line.strip().partition(":")
        environment[key.strip()] = value.strip().strip('"').strip("'")
    return environment


def _service_image(service: str) -> str:
    """Return the image reference of one service from the compose file."""
    lines = COMPOSE_FILE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  {service}:")), None)
    assert start is not None, f"service {service} not found in {COMPOSE_FILE}"
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        if line.strip().startswith("image:"):
            return line.split("image:", 1)[1].strip()
    raise AssertionError(f"service {service} has no image")


def _service_block(path: Path, service: str) -> str:
    """Return the text of one service block in a compose file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  {service}:")), None)
    assert start is not None, f"service {service} not found in {path}"
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line)
    return "\n".join(block)


def _service_ports(service: str) -> list[str]:
    """Return the published port entries of one service from the compose file."""
    lines = COMPOSE_FILE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  {service}:")), None)
    assert start is not None, f"service {service} not found in {COMPOSE_FILE}"
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line)
    try:
        ports_at = next(i for i, line in enumerate(block) if line.strip() == "ports:")
    except StopIteration:  # pragma: no cover - defensive
        raise AssertionError(f"service {service} has no ports block") from None
    entries: list[str] = []
    for line in block[ports_at + 1 :]:
        if not line.strip():
            continue
        if not line.startswith("      - "):
            break
        entries.append(line.strip()[2:].strip().strip('"').strip("'"))
    return entries


def _env_example_text() -> str:
    """The text of the repository-root environment template."""
    return ENV_EXAMPLE.read_text(encoding="utf-8")


def _backend_env_example_text() -> str:
    """The text of the backend component's environment template."""
    return BACKEND_ENV_EXAMPLE.read_text(encoding="utf-8")


def _architecture_section_9() -> str:
    """The text of the configuration table in ARCHITECTURE.md section 9."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    start = text.index("## 9. Cross-cutting concerns")
    end = text.index("## 10. Decisions and tradeoffs")
    return text[start:end]


def _resolve(template: str) -> tuple[str, str]:
    """Return the (variable, default) pair of a ${VAR:-default} compose value."""
    assert template.startswith("${") and template.endswith("}"), template
    variable, _, default = template[2:-1].partition(":-")
    return variable, default


def test_inference_alias_matches_the_model_id_the_backend_sends() -> None:
    """The served model id and the requested model id are the same string."""
    inference = _service_environment("inference-chat")
    backend = _service_environment("backend")
    alias_var, alias_default = _resolve(inference["LLAMA_ARG_ALIAS"])
    model_var, model_default = _resolve(backend["DELPHOS_LLM_MODEL_NAME"])
    assert alias_var == model_var, "the alias and the requested id must share one variable"
    assert alias_default == DEFAULT_MODEL_ID
    assert model_default == DEFAULT_MODEL_ID


def test_backend_model_id_is_environment_overridable() -> None:
    """The backend model id keeps a default but can be overridden."""
    backend = _service_environment("backend")
    assert backend["DELPHOS_LLM_MODEL_NAME"] == f"${{DELPHOS_LLM_MODEL_NAME:-{DEFAULT_MODEL_ID}}}"


def test_inference_model_path_is_environment_overridable() -> None:
    """The same compose file serves the CUDA and the CPU model variant."""
    inference = _service_environment("inference-chat")
    assert inference["LLAMA_ARG_MODEL"] == f"${{LLAMA_ARG_MODEL:-{DEFAULT_MODEL_PATH}}}"


def test_inference_image_tag_is_environment_overridable() -> None:
    """The same compose file serves the CUDA and the CPU build of the server."""
    image = _service_image("inference-chat")

    repository, _, tag = image.partition(":")
    assert repository == "ghcr.io/ggml-org/llama.cpp"
    variable, default = _resolve(tag)
    assert variable == "LLAMA_ARG_IMAGE"
    assert default == "server-cuda"


def test_env_example_documents_the_inference_variables() -> None:
    """The environment template names the variables compose reads."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "LLAMA_ARG_MODEL" in text
    assert "LLAMA_ARG_IMAGE" in text
    assert "DELPHOS_LLM_MODEL_NAME" in text
    assert "DELPHOS_LLM_API_URL" in text
    assert "DELPHOS_INFERENCE_PUBLISH_IP" in text
    assert "DELPHOS_INFERENCE_PUBLISH_PORT" in text


def test_inference_publishes_on_the_documented_address_and_port() -> None:
    """The compose template carries the documented publish address and port."""
    entries = _service_ports("inference-chat")
    assert len(entries) == 1, "the inference service publishes exactly one port"
    assert entries[0] == (
        "${DELPHOS_INFERENCE_PUBLISH_IP:-" + DEFAULT_PUBLISH_IP + "}"
        ":${DELPHOS_INFERENCE_PUBLISH_PORT:-" + DEFAULT_PUBLISH_PORT + "}"
        ":" + INFERENCE_CONTAINER_PORT
    )


def test_env_example_publish_defaults_match_the_compose_defaults() -> None:
    """The documented defaults and the compose defaults are the same strings."""
    entry = _service_ports("inference-chat")[0]
    match = _PUBLISH_ENTRY.fullmatch(entry)
    assert match is not None, f"unexpected publish entry: {entry}"
    assert match["ip_variable"] == "DELPHOS_INFERENCE_PUBLISH_IP"
    assert match["port_variable"] == "DELPHOS_INFERENCE_PUBLISH_PORT"
    assert match["ip_default"] == DEFAULT_PUBLISH_IP
    assert match["port_default"] == DEFAULT_PUBLISH_PORT

    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert f"# DELPHOS_INFERENCE_PUBLISH_IP={match['ip_default']}" in text
    assert f"# DELPHOS_INFERENCE_PUBLISH_PORT={match['port_default']}" in text


def test_cpu_override_removes_the_gpu_request() -> None:
    """The CPU variant resets the GPU request, so it can start without a card."""
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "    gpus: all" in compose, "the base file requests the GPU"

    override = REPO_ROOT / "docker-compose.cpu.yml"
    assert override.exists(), "the CPU override file is part of the deployment"
    block = _service_block(override, "inference-chat")
    assert "gpus: !reset null" in block, "the override resets the key for that service"


def test_the_backend_service_forwards_the_fallback_keys() -> None:
    """The fallback keys reach the container, so they take effect in the compose stack."""
    backend = _service_environment("backend")

    assert backend["DELPHOS_LLM_FALLBACK_API_URL"] == "${DELPHOS_LLM_FALLBACK_API_URL:-}"
    assert backend["DELPHOS_LLM_FALLBACK_MODEL_NAME"] == "${DELPHOS_LLM_FALLBACK_MODEL_NAME:-}"
    assert backend["DELPHOS_LLM_FALLBACK_TIMEOUT_SECONDS"] == (
        "${DELPHOS_LLM_FALLBACK_TIMEOUT_SECONDS:-60.0}"
    )
    assert backend["DELPHOS_LLM_FALLBACK_PEER_CIDR"] == (
        "${DELPHOS_LLM_FALLBACK_PEER_CIDR:-10.0.0.0/8}"
    )
    assert (
        backend["DELPHOS_LLM_PRIMARY_PROBE_SECONDS"] == "${DELPHOS_LLM_PRIMARY_PROBE_SECONDS:-5.0}"
    )
    assert backend["DELPHOS_INFERENCE_PUBLISH_IP"] == "${DELPHOS_INFERENCE_PUBLISH_IP:-127.0.0.1}"


def test_the_env_template_and_the_architecture_table_name_the_same_keys() -> None:
    """`.env.example` and ARCHITECTURE.md §9 agree, in both directions."""
    env_keys = set(re.findall(r"^#\s*([A-Z][A-Z0-9_]*)=", _env_example_text(), re.M))
    arch_keys = set(re.findall(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|", _architecture_section_9(), re.M))

    assert env_keys - arch_keys == set(), "a key of the template is missing in §9"
    assert arch_keys - env_keys == set(), "a key of §9 is missing in the template"


def test_the_prompt_version_default_is_the_same_everywhere() -> None:
    """The code, both environment templates and §9 name one prompt revision.

    The revision is the report cache's key, so a template that names another
    one would ship a cache key the code never produces.
    """
    from delphos_backend.core.config import Settings

    default = Settings().llm_report_prompt_version
    assert default == PROMPT_VERSION_DEFAULT
    assert f"# {PROMPT_VERSION_KEY}={default}" in _env_example_text()
    assert f"# {PROMPT_VERSION_KEY}={default}" in _backend_env_example_text()
    assert f"| `{PROMPT_VERSION_KEY}` | `{default}` |" in _architecture_section_9()
