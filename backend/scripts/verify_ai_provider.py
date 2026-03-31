from __future__ import annotations

import asyncio
import sys
from unittest.mock import patch

sys.path.insert(0, "/workspace")

from backend.app.core.ai import build_ai_provider
from backend.app.core.config import Settings


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    def __init__(self, *, payload: dict, capture: dict[str, object], **_: object) -> None:
        self._payload = payload
        self._capture = capture

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        self._capture["url"] = url
        self._capture["json"] = json
        self._capture["headers"] = headers
        return FakeResponse(self._payload)


async def verify_qwen() -> None:
    capture: dict[str, object] = {}
    settings = Settings(
        ai_backend="qwen_api",
        qwen_api_url="https://qwen.example/api",
        qwen_api_key="secret-key",
        qwen_model="qwen-plus",
    )
    provider = build_ai_provider(settings)
    with patch(
        "backend.app.core.ai.httpx.AsyncClient",
        side_effect=lambda *args, **kwargs: FakeAsyncClient(
            payload={"choices": [{"message": {"content": "Qwen OK"}}]},
            capture=capture,
            **kwargs,
        ),
    ):
        result = await provider.generate(system_prompt="sys", user_prompt="hello")

    assert result.provider == "qwen_api:qwen-plus"
    assert result.content == "Qwen OK"
    assert capture["url"] == "https://qwen.example/api/v1/chat/completions"
    assert capture["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-key",
    }


async def verify_ollama() -> None:
    capture: dict[str, object] = {}
    settings = Settings(
        ai_backend="ollama",
        ollama_base_url="http://ollama.internal:11434",
        ollama_model="qwen2.5:7b",
    )
    provider = build_ai_provider(settings)
    with patch(
        "backend.app.core.ai.httpx.AsyncClient",
        side_effect=lambda *args, **kwargs: FakeAsyncClient(
            payload={"message": {"content": "Ollama OK"}},
            capture=capture,
            **kwargs,
        ),
    ):
        result = await provider.generate(system_prompt="sys", user_prompt="hello")

    assert result.provider == "ollama:qwen2.5:7b"
    assert result.content == "Ollama OK"
    assert capture["url"] == "http://ollama.internal:11434/api/chat"


async def main() -> None:
    disabled = build_ai_provider(Settings(ai_backend="disabled"))
    assert disabled.provider == "disabled"
    await verify_qwen()
    await verify_ollama()
    print("PASS: AI provider abstraction switches between disabled, Qwen API, and Ollama")


if __name__ == "__main__":
    asyncio.run(main())
