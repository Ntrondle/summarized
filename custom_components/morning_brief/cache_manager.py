"""Cache management for generated Morning Brief audio."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import logging

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import STATIC_CACHE_PATH, TEMP_AUDIO_PREFIX

_LOGGER = logging.getLogger(__name__)


class CacheManager:
    """Manage a single cached audio file."""

    def __init__(self, hass: HomeAssistant, cache_dir: Path) -> None:
        """Initialize the cache manager."""
        self.hass = hass
        self.cache_dir = cache_dir
        self._cached_path: Path | None = None
        self._cached_at = None

    async def async_prepare(self) -> None:
        """Ensure the cache directory exists and starts clean on boot."""
        await self.hass.async_add_executor_job(
            lambda: self.cache_dir.mkdir(parents=True, exist_ok=True)
        )
        await self.async_clear()

    async def async_get_valid_cache(self, ttl_minutes: int) -> Path | None:
        """Return the cached audio path if it is still valid."""
        if self._cached_path is None or self._cached_at is None:
            return None

        if not await self.hass.async_add_executor_job(self._cached_path.exists):
            self._cached_path = None
            self._cached_at = None
            return None

        age = dt_util.utcnow() - self._cached_at
        if age > timedelta(minutes=ttl_minutes):
            return None

        return self._cached_path

    async def async_store_audio(self, audio_bytes: bytes) -> Path:
        """Replace the cached audio file with a new one."""
        await self.async_clear()

        filename = f"{TEMP_AUDIO_PREFIX}{int(dt_util.utcnow().timestamp())}.mp3"
        path = self.cache_dir / filename

        await self.hass.async_add_executor_job(path.write_bytes, audio_bytes)
        self._cached_path = path
        self._cached_at = dt_util.utcnow()
        _LOGGER.debug("Stored generated audio in cache at %s", path)
        return path

    async def async_clear(self) -> None:
        """Remove all cached audio files."""
        for path in await self.hass.async_add_executor_job(
            lambda: list(self.cache_dir.glob("*.mp3"))
        ):
            try:
                await self.hass.async_add_executor_job(path.unlink, True)
            except FileNotFoundError:
                continue
            except OSError as err:
                _LOGGER.warning("Failed to delete cached audio file %s: %s", path, err)

        self._cached_path = None
        self._cached_at = None

    def build_public_url(self, audio_path: Path) -> str:
        """Build the public URL for a cached audio file."""
        return f"{STATIC_CACHE_PATH}/{audio_path.name}"
