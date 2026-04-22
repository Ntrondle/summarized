"""Media player control helpers for Morning Brief."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from homeassistant.const import (
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network

from .const import (
    DEFAULT_PLAYBACK_TIMEOUT_SECONDS,
    DEFAULT_WAIT_STEP_SECONDS,
    GENERATED_AUDIO_CONTENT_TYPE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MediaSnapshot:
    """State snapshot for restoring previous playback."""

    media_content_id: str
    media_content_type: str
    media_position: float | None
    initial_state: str


class MediaController:
    """Control media playback around the generated brief."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the controller."""
        self.hass = hass

    async def async_play_generated_audio(
        self,
        entity_id: str,
        relative_audio_url: str,
    ) -> None:
        """Pause current playback, play the generated audio, then restore."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            _LOGGER.error("Speaker %s is unavailable", entity_id)
            raise RuntimeError(f"Speaker {entity_id} is unavailable")

        audio_url = self._build_absolute_url(relative_audio_url)
        snapshot = await self._async_capture_snapshot(entity_id)

        if snapshot and snapshot.initial_state == STATE_PLAYING:
            await self._async_call_media_service("media_pause", entity_id)
            await self._async_wait_for_state(entity_id, {STATE_PAUSED, STATE_IDLE, STATE_OFF}, 15)

        await self._async_call_media_service(
            "play_media",
            entity_id,
            {
                "media_content_id": audio_url,
                "media_content_type": GENERATED_AUDIO_CONTENT_TYPE,
                "extra": {"title": "Morning Brief"},
            },
        )

        await self._async_wait_for_audio_completion(entity_id, audio_url)

        if snapshot:
            await self._async_restore_previous_media(entity_id, snapshot)

    def _build_absolute_url(self, relative_audio_url: str) -> str:
        """Build an absolute URL that the speaker can fetch."""
        try:
            base_url = network.get_url(self.hass)
        except network.NoURLAvailableError as err:
            _LOGGER.error("No Home Assistant URL is configured for audio playback")
            raise RuntimeError(
                "Home Assistant needs an internal or external URL configured to serve audio"
            ) from err

        return f"{base_url}{relative_audio_url}"

    async def _async_capture_snapshot(self, entity_id: str) -> MediaSnapshot | None:
        """Capture current playback state when it can be restored later."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return None

        if state.state in {STATE_IDLE, STATE_OFF, STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None

        media_content_id = state.attributes.get("media_content_id")
        if not media_content_id:
            return None

        return MediaSnapshot(
            media_content_id=media_content_id,
            media_content_type=state.attributes.get("media_content_type", GENERATED_AUDIO_CONTENT_TYPE),
            media_position=state.attributes.get("media_position"),
            initial_state=state.state,
        )

    async def _async_restore_previous_media(
        self,
        entity_id: str,
        snapshot: MediaSnapshot,
    ) -> None:
        """Restore the interrupted media session."""
        try:
            await self._async_call_media_service(
                "play_media",
                entity_id,
                {
                    "media_content_id": snapshot.media_content_id,
                    "media_content_type": snapshot.media_content_type,
                },
            )
            await self._async_wait_for_state(
                entity_id,
                {STATE_PLAYING, STATE_BUFFERING, STATE_PAUSED, STATE_IDLE},
                30,
            )

            if snapshot.media_position is not None:
                await self._async_call_media_service(
                    "media_seek",
                    entity_id,
                    {"seek_position": snapshot.media_position},
                )

            if snapshot.initial_state == STATE_PAUSED:
                await self._async_call_media_service("media_pause", entity_id)
            else:
                await self._async_call_media_service("media_play", entity_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to restore previous media on %s: %s", entity_id, err)

    async def _async_wait_for_audio_completion(
        self,
        entity_id: str,
        audio_url: str,
    ) -> None:
        """Wait until the generated audio has stopped playing."""
        deadline = asyncio.get_running_loop().time() + DEFAULT_PLAYBACK_TIMEOUT_SECONDS

        while asyncio.get_running_loop().time() < deadline:
            state = self.hass.states.get(entity_id)
            if state is None:
                return

            current_media = state.attributes.get("media_content_id")
            if current_media != audio_url and state.state not in {STATE_BUFFERING, STATE_PLAYING}:
                return

            if state.state in {STATE_IDLE, STATE_OFF, STATE_PAUSED} and current_media != audio_url:
                return

            await asyncio.sleep(DEFAULT_WAIT_STEP_SECONDS)

        _LOGGER.warning("Timed out waiting for generated audio to finish on %s", entity_id)

    async def _async_wait_for_state(
        self,
        entity_id: str,
        target_states: set[str],
        timeout_seconds: int,
    ) -> None:
        """Poll until a media player reaches a target state."""
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state in target_states:
                return
            await asyncio.sleep(DEFAULT_WAIT_STEP_SECONDS)

    async def _async_call_media_service(
        self,
        service: str,
        entity_id: str,
        extra_data: dict | None = None,
    ) -> None:
        """Call a media_player service."""
        data = {"entity_id": entity_id}
        if extra_data:
            data.update(extra_data)

        await self.hass.services.async_call(
            "media_player",
            service,
            data,
            blocking=True,
        )

