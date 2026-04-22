"""ElevenLabs text-to-speech client for Morning Brief."""

from __future__ import annotations

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
        except httpx.HTTPError as err:
            _LOGGER.error("ElevenLabs TTS request failed: %s", err)
            raise RuntimeError(f"ElevenLabs TTS request failed: {err}") from err

        if not response.content:
            _LOGGER.error("ElevenLabs returned an empty audio payload")
            raise RuntimeError("ElevenLabs returned an empty audio payload")

        return response.content

