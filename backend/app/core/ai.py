from __future__ import annotations

from dataclasses import dataclass

import httpx

from backend.app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AICompletionResult:
    content: str
    provider: str


class BaseAIProvider:
    provider: str

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> AICompletionResult:
        raise NotImplementedError


class DisabledAIProvider(BaseAIProvider):
    provider = "disabled"

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> AICompletionResult:
        raise RuntimeError("AI backend is not configured")


class QwenAPIProvider(BaseAIProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.qwen_api_url:
            raise RuntimeError("QWEN_API_URL is not configured")
        self._endpoint = _normalize_qwen_endpoint(settings.qwen_api_url)
        self._api_key = settings.qwen_api_key
        self._model = settings.qwen_model
        self._timeout = settings.ai_timeout_seconds
        self.provider = f"qwen_api:{self._model}"

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> AICompletionResult:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise RuntimeError("Empty response from Qwen API provider")
        return AICompletionResult(content=content, provider=self.provider)


class OllamaProvider(BaseAIProvider):
    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.ollama_base_url.rstrip("/") + "/api/chat"
        self._model = settings.ollama_model
        self._timeout = settings.ai_timeout_seconds
        self.provider = f"ollama:{self._model}"

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> AICompletionResult:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("message", {}).get("content")
            or data.get("response", "")
        ).strip()
        if not content:
            raise RuntimeError("Empty response from Ollama provider")
        return AICompletionResult(content=content, provider=self.provider)


def _normalize_qwen_endpoint(url: str) -> str:
    normalized = url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/chat/completions"
    return normalized + "/v1/chat/completions"


def build_ai_provider(settings: Settings | None = None) -> BaseAIProvider:
    resolved = settings or get_settings()
    backend = resolved.ai_backend.strip().lower()
    if backend == "qwen_api":
        return QwenAPIProvider(resolved)
    if backend == "ollama":
        return OllamaProvider(resolved)
    return DisabledAIProvider()
