from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class LLMProviderConfig:
    provider_name: str = "DeepSeek V4 Pro"
    base_url: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-v4-pro"
    embedding_model: str = "deepseek-embedding"
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    request_timeout_seconds: float = 180.0


class DeepSeekProvider:
    """Reserved abstraction for future real LLM calls."""

    def __init__(self, config: LLMProviderConfig | None = None) -> None:
        self.config = config or LLMProviderConfig()

    def describe(self) -> dict[str, str]:
        return {
            "provider_name": self.config.provider_name,
            "base_url": self.config.base_url,
            "chat_model": self.config.chat_model,
            "embedding_model": self.config.embedding_model,
        }

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.config.request_timeout_seconds, trust_env=False) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("DeepSeek 返回结构不符合预期") from exc
