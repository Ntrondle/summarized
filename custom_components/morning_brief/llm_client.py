"""z.ai chat completion client for Morning Brief."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)


class ZAIClient:
    """Minimal z.ai chat completion client."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        """Initialize the client."""
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def async_summarize_topic(
        self,
        client: httpx.AsyncClient,
        topic_name: str,
        topic_prompt: str,
        items: list[dict[str, Any]],
    ) -> str:
        """Generate a summary for a single topic."""
        user_content = json.dumps(
            {
                "topic": topic_name,
                "items": items,
            },
            ensure_ascii=True,
            indent=2,
        )
        return await self._async_chat_completion(
            client,
            system_prompt=topic_prompt,
            user_content=user_content,
        )

    async def async_assemble_brief(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        topic_summaries: list[dict[str, str]],
    ) -> str:
        """Assemble the final brief from the per-topic summaries."""
        user_content = json.dumps(
            {"topic_summaries": topic_summaries},
            ensure_ascii=True,
            indent=2,
        )
        return await self._async_chat_completion(
            client,
            system_prompt=system_prompt,
            user_content=user_content,
        )

    async def _async_chat_completion(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_content: str,
    ) -> str:
        """Call the z.ai chat completions endpoint."""
        url = self._build_chat_completion_url()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as err:
            _LOGGER.error("z.ai request failed: %s", err)
            raise RuntimeError(f"z.ai request failed: {err}") from err

        data = response.json()
        content = self._extract_message_content(data)
        if not content:
            _LOGGER.error("z.ai returned an empty response body")
            raise RuntimeError("z.ai returned an empty response")

        return content.strip()

    def _build_chat_completion_url(self) -> str:
        """Build the full chat completion endpoint URL."""
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"

    def _extract_message_content(self, response_data: dict[str, Any]) -> str:
        """Extract assistant text from the z.ai response."""
        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as err:
            raise RuntimeError("z.ai response format was not recognized") from err

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "\n".join(part for part in parts if part)

        return str(content)

