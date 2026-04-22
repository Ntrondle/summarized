"""ElevenLabs text-to-speech client for Morning Brief."""

from __future__ import annotations

import json
import logging

import httpx

from .const import TTS_LANGUAGE_CODE

_LOGGER = logging.getLogger(__name__)


class ElevenLabsTTSClient:
    """Generate speech with ElevenLabs."""

    def __init__(self, api_key: str) -> None:
        """Initialize the TTS client."""
        self._api_key = api_key

    async def async_generate_audio(
        self,
        client: httpx.AsyncClient,
        *,
        text: str,
        voice_id: str,
        model_id: str,
    ) -> bytes:
        """Generate audio bytes from text."""
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            "?output_format=mp3_44100_128"
        )
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "language_code": TTS_LANGUAGE_CODE,
        }

        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            message = self._build_error_message(err, voice_id, model_id)
            _LOGGER.error("ElevenLabs TTS request failed: %s", message)
            raise RuntimeError(f"ElevenLabs TTS request failed: {message}") from err
        except httpx.RequestError as err:
            message = self._build_request_error_message(err)
            _LOGGER.error("ElevenLabs TTS request failed: %s", message)
            raise RuntimeError(f"ElevenLabs TTS request failed: {message}") from err

        if not response.content:
            _LOGGER.error("ElevenLabs returned an empty audio payload")
            raise RuntimeError("ElevenLabs returned an empty audio payload")

        return response.content

    def _build_error_message(
        self,
        err: httpx.HTTPStatusError,
        voice_id: str,
        model_id: str,
    ) -> str:
        """Build a detailed ElevenLabs error message."""
        response = err.response
        request_id = self._get_request_id(response)
        detail_message = self._extract_detail_message(response)
        status_code = response.status_code

        message = f"HTTP {status_code} for model '{model_id}' and voice '{voice_id}'"
        if detail_message:
            message = f"{message}: {detail_message}"
        else:
            message = f"{message}: {response.text.strip() or str(err)}"

        if status_code == 402:
            message = (
                f"{message}. On the ElevenLabs free tier, this often means the selected "
                "voice is not usable via the API, especially if it comes from the Voice "
                "Library or has a credit multiplier."
            )

        if request_id:
            message = f"{message} (request id: {request_id})"

        return message

    def _build_request_error_message(self, err: httpx.RequestError) -> str:
        """Build a useful network error message."""
        request_url = err.request.url if err.request else "https://api.elevenlabs.io/"
        details = str(err).strip() or err.__class__.__name__
        return f"{details} for url '{request_url}'"

    def _extract_detail_message(self, response: httpx.Response) -> str | None:
        """Extract the JSON detail message returned by ElevenLabs."""
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return None

        detail = data.get("detail")
        if isinstance(detail, dict):
            message = detail.get("message")
            code = detail.get("code")
            error_type = detail.get("type")
            parts = [part for part in (error_type, code, message) if part]
            if parts:
                return " / ".join(str(part) for part in parts)
            return None

        if isinstance(detail, str):
            return detail

        return None

    def _get_request_id(self, response: httpx.Response) -> str | None:
        """Extract a request identifier from common response headers or body."""
        for header in ("request-id", "x-request-id"):
            value = response.headers.get(header)
            if value:
                return value

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return None

        detail = data.get("detail")
        if isinstance(detail, dict):
            request_id = detail.get("request_id")
            if request_id:
                return str(request_id)

        return None
