"""z.ai chat completion client for Morning Brief."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_RETRY_DELAY_SECONDS = 2.0


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
            {
                "instruction": (
                    "Voici des resumes intermediaires deja generes a partir des flux RSS. "
                    "Ne lis pas cette structure JSON. Utilise uniquement le prompt systeme "
                    "pour transformer ces resumes en brief final naturel, fluide et pret "
                    "pour une synthese vocale."
                ),
                "topic_summaries": topic_summaries,
            },
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

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                break
            except httpx.TimeoutException as err:
                message = self._build_timeout_message(err, url)
                _LOGGER.error("z.ai request timed out: %s", message)
                raise RuntimeError(message) from err
            except httpx.HTTPStatusError as err:
                if err.response.status_code == 429 and attempt < _MAX_RETRIES:
                    delay = self._get_retry_delay(err.response, attempt)
                    _LOGGER.warning(
                        "z.ai rate limit reached, retrying in %.1f seconds (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                message = self._build_error_message(err)
                _LOGGER.error("z.ai request failed: %s", message)
                raise RuntimeError(f"z.ai request failed: {message}") from err
            except httpx.RequestError as err:
                message = self._build_request_error_message(err)
                _LOGGER.error("z.ai request failed: %s", message)
                raise RuntimeError(f"z.ai request failed: {message}") from err

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

    def _get_retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Return the retry delay using Retry-After when available."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), _BASE_RETRY_DELAY_SECONDS)
            except ValueError:
                pass

        return _BASE_RETRY_DELAY_SECONDS * (2**attempt)

    def _build_error_message(self, err: httpx.HTTPStatusError) -> str:
        """Build a more useful error message from the HTTP response."""
        response = err.response
        response_text = response.text.strip()
        request_id = self._get_request_id(response)
        if response_text:
            message = (
                f"HTTP {response.status_code} for url '{response.request.url}': "
                f"{response_text}"
            )
            if request_id:
                message = f"{message} (request id: {request_id})"
            return message

        message = str(err)
        if request_id:
            message = f"{message} (request id: {request_id})"
        return message

    def _build_timeout_message(self, err: httpx.TimeoutException, url: str) -> str:
        """Build a useful timeout message."""
        timeout = "configured"
        if err.request is not None:
            timeout_config = err.request.extensions.get("timeout")
            if isinstance(timeout_config, dict) and timeout_config.get("read") is not None:
                timeout = str(timeout_config["read"])

        return (
            "z.ai request timed out before a response was returned "
            f"for url '{url}' (read timeout: {timeout}s). "
            "The request may be too slow or the provider may be rate-limiting."
        )

    def _build_request_error_message(self, err: httpx.RequestError) -> str:
        """Build a useful network error message."""
        request_url = err.request.url if err.request else self._build_chat_completion_url()
        details = str(err).strip() or err.__class__.__name__
        return f"{details} for url '{request_url}'"

    def _get_request_id(self, response: httpx.Response) -> str | None:
        """Extract a request identifier from common response headers."""
        for header in ("x-request-id", "request-id", "x-amzn-requestid"):
            value = response.headers.get(header)
            if value:
                return value
        return None
