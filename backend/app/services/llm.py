from typing import Protocol

import httpx
from pydantic import BaseModel

DEFAULT_TIMEOUT = 120.0


class GenerateOptions(BaseModel):
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    json_mode: bool = False


class LLMClient(Protocol):
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        options: GenerateOptions | None = None,
    ) -> str: ...


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/chat/completions"


class OllamaLLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.transport = transport

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        options: GenerateOptions | None = None,
    ) -> str:
        opts = options or GenerateOptions()
        model = opts.model or self.model
        body = {
            "model": model,
            "messages": messages,
            "temperature": opts.temperature,
        }
        if opts.max_tokens is not None:
            body["max_tokens"] = opts.max_tokens
        if opts.json_mode:
            body["response_format"] = {"type": "json_object"}

        url = _chat_completions_url(self.base_url)
        client_kw = {"timeout": self.timeout}
        if self.transport is not None:
            client_kw["transport"] = self.transport
        with httpx.Client(**client_kw) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if isinstance(content, str) else str(content).strip()


class MockLLMClient:
    def __init__(self, response: str = "Mock LLM response"):
        self.response = response

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        options: GenerateOptions | None = None,
    ) -> str:
        return self.response


def get_llm_client(settings=None):
    from app.config import Settings
    s = settings or Settings()
    return OllamaLLMClient(s.ollama_base_url, s.ollama_model)
