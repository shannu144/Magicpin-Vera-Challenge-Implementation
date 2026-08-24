from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> Optional[Dict[str, Any]]:
        pass


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return json.loads(content)
        except Exception:
            return None
        return None


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"System:\n{system_prompt}\n\nUser:\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
        except Exception:
            return None
        return None


class LLMService:
    def __init__(self):
        self.provider: Optional[BaseLLMProvider] = None
        self._init_provider()

    def _init_provider(self):
        provider_name = settings.llm_provider.lower()
        api_key = settings.llm_api_key or os.getenv("OPENAI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

        if provider_name == "openai" or (not provider_name and os.getenv("OPENAI_API_KEY")):
            self.provider = OpenAIProvider(api_key=api_key, model=settings.model)
        elif provider_name in ("gemini", "google"):
            self.provider = GeminiProvider(api_key=api_key, model=settings.model)
        else:
            self.provider = None

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Optional[Dict[str, Any]]:
        if not self.provider:
            return None
        return await self.provider.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )


llm_service = LLMService()
