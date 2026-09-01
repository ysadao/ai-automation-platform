from __future__ import annotations

import hashlib
import os
from typing import Any


class MockAIProvider:
    """Deterministic stand-in for a hosted LLM. Never calls the network.

    A future OpenAIProvider can be selected when OPENAI_API_KEY is set;
    this portfolio build always returns mock completions so tests and demos
    stay offline and repeatable.
    """

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


def get_provider() -> MockAIProvider:
    _ = os.environ.get("OPENAI_API_KEY")
    return MockAIProvider()
