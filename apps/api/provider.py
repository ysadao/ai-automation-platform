from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol


class Provider(Protocol):
    model: str

    def complete(self, prompt: str) -> dict[str, Any]:
        ...


class MockAIProvider:
    """Deterministic stand-in for a hosted LLM. Never calls the network."""

    model = "mock-ink-1"

    def complete(self, prompt: str) -> dict[str, Any]:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        excerpt = " ".join(prompt.split())[:120]
        text = (
            f"[mock-{digest[:8]}] {self.model} processed {len(prompt)} chars. "
            f"Lead: {excerpt}"
        )
        tokens_in = max(1, len(prompt) // 4)
        tokens_out = max(1, len(text) // 4)
        return {
            "text": text,
            "tokensIn": tokens_in,
            "tokensOut": tokens_out,
            "model": self.model,
            "digest": digest[:16],
        }


class OpenAIProvider:
    """Live OpenAI chat completions. Instantiated only when OPENAI_API_KEY is set."""

    model = "gpt-4o-mini"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def complete(self, prompt: str) -> dict[str, Any]:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return {
            "text": text,
            "tokensIn": int(usage.get("prompt_tokens") or 0),
            "tokensOut": int(usage.get("completion_tokens") or 0),
            "model": data.get("model") or self.model,
            "digest": None,
        }


def get_provider() -> Provider:
    key = os.environ.get("OPENAI_API_KEY") or ""
    if key.strip():
        return OpenAIProvider(api_key=key.strip())
    return MockAIProvider()
