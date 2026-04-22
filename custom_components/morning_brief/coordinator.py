"""Main orchestration logic for Morning Brief."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from homeassistant.core import HomeAssistant

from .cache_manager import CacheManager
from .const import (
    ATTR_ELEVENLABS_MODEL,
    ATTR_ELEVENLABS_VOICE_ID,
    ATTR_SPEAKER_ENTITY_ID,
    CONF_CACHE_ENABLED,
    CONF_CACHE_TTL_MINUTES,
    CONF_RSS_LOOKBACK_DAYS,
    CONF_SYSTEM_PROMPT,
    CONF_TOPICS,
)
from .llm_client import ZAIClient
from .media_controller import MediaController
from .rss_fetcher import RSSFetcher
from .tts_client import ElevenLabsTTSClient

_LOGGER = logging.getLogger(__name__)


class MorningBriefCoordinator:
    """Run the full Morning Brief pipeline."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config: dict[str, Any],
        cache_manager: CacheManager,
        rss_fetcher: RSSFetcher,
        llm_client: ZAIClient,
        tts_client: ElevenLabsTTSClient,
        media_controller: MediaController,
        http_client: httpx.AsyncClient,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config = config
        self.cache_manager = cache_manager
        self.rss_fetcher = rss_fetcher
        self.llm_client = llm_client
        self.tts_client = tts_client
        self.media_controller = media_controller
        self.http_client = http_client

    async def async_generate_and_play(
        self,
        *,
        speaker_entity_id: str,
        elevenlabs_voice_id: str,
        elevenlabs_model: str,
    ) -> None:
        """Generate or reuse a brief, then play it."""
        audio_path = None

        if self.config.get(CONF_CACHE_ENABLED, False):
            audio_path = await self.cache_manager.async_get_valid_cache(
                self.config[CONF_CACHE_TTL_MINUTES]
            )
            if audio_path:
                _LOGGER.debug("Reusing cached Morning Brief audio from %s", audio_path)

        if audio_path is None:
            topic_data = await self.rss_fetcher.async_fetch_topics(
                self.config[CONF_TOPICS],
                self.config[CONF_RSS_LOOKBACK_DAYS],
            )
            if not topic_data:
                raise RuntimeError("No RSS items were available for any configured topic")

            summaries = await asyncio.gather(
                *[
                    self._async_summarize_topic(topic)
                    for topic in topic_data
                ]
            )
            if not summaries:
                raise RuntimeError("No topic summaries were generated")

            final_brief = await self.llm_client.async_assemble_brief(
                self.http_client,
                self.config[CONF_SYSTEM_PROMPT],
                summaries,
            )
            if not final_brief:
                raise RuntimeError("The final Morning Brief was empty")

            audio_bytes = await self.tts_client.async_generate_audio(
                self.http_client,
                text=final_brief,
                voice_id=elevenlabs_voice_id,
                model_id=elevenlabs_model,
            )
            audio_path = await self.cache_manager.async_store_audio(audio_bytes)

        await self.media_controller.async_play_generated_audio(
            speaker_entity_id,
            self.cache_manager.build_public_url(audio_path),
        )

    async def _async_summarize_topic(self, topic: dict[str, Any]) -> dict[str, str]:
        """Generate a summary block for one topic."""
        summary = await self.llm_client.async_summarize_topic(
            self.http_client,
            topic["name"],
            topic["topic_prompt"],
            topic["items"],
        )
        return {"name": topic["name"], "summary": summary}

