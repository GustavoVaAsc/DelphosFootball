"""Consistency tests for the deployment files (docker-compose.yml, .env.example).

Input: the compose file and the environment template at the repository root.
Output: assertions on the rendered service environment.
Responsibility: keeps the model id the backend sends identical to the model id
the inference server serves, so a request can never fail to resolve its model.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

DEFAULT_MODEL_ID = "qwen/qwen3.5-9b"
DEFAULT_MODEL_PATH = "/models/Qwen3.5-9B-Q5_K_M.gguf"


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
