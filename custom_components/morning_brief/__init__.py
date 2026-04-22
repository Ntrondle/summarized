"""Morning Brief Home Assistant integration."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any
import logging

import httpx
import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .cache_manager import CacheManager
from .const import (
    ATTR_ELEVENLABS_MODEL,
    ATTR_ELEVENLABS_VOICE_ID,
    ATTR_SPEAKER_ENTITY_ID,
    DEFAULT_CACHE_ENABLED,
    DEFAULT_CACHE_TTL_MINUTES,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_RSS_LOOKBACK_DAYS,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_ZAI_BASE_URL,
    DEFAULT_ZAI_MODEL,
    CONF_CACHE_ENABLED,
    CONF_CACHE_TTL_MINUTES,
    CONF_ELEVENLABS_API_KEY,
    CONF_RSS_LOOKBACK_DAYS,
    CONF_SYSTEM_PROMPT,
    CONF_TOPICS,
    CONF_TOPIC_FEEDS,
    CONF_TOPIC_NAME,
    CONF_TOPIC_PROMPT,
    CONF_ZAI_API_KEY,
    CONF_ZAI_BASE_URL,
    CONF_ZAI_MODEL,
    DATA_CACHE_DIR,
    DATA_SERVICE_REGISTERED,
    DATA_STATIC_REGISTERED,
    DOMAIN,
    SERVICE_GENERATE,
)
from .coordinator import MorningBriefCoordinator
from .llm_client import ZAIClient
from .media_controller import MediaController
from .rss_fetcher import RSSFetcher
from .tts_client import ElevenLabsTTSClient

_LOGGER = logging.getLogger(__name__)

TOPIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOPIC_NAME): cv.string,
        vol.Required(CONF_TOPIC_PROMPT): cv.string,
        vol.Required(CONF_TOPIC_FEEDS): vol.All(cv.ensure_list, [cv.url]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_ZAI_API_KEY): cv.string,
                vol.Optional(CONF_ZAI_BASE_URL, default=DEFAULT_ZAI_BASE_URL): cv.string,
                vol.Optional(CONF_ZAI_MODEL, default=DEFAULT_ZAI_MODEL): cv.string,
                vol.Required(CONF_ELEVENLABS_API_KEY): cv.string,
                vol.Optional(
                    CONF_RSS_LOOKBACK_DAYS,
                    default=DEFAULT_RSS_LOOKBACK_DAYS,
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(CONF_CACHE_ENABLED, default=DEFAULT_CACHE_ENABLED): cv.boolean,
                vol.Optional(
                    CONF_CACHE_TTL_MINUTES,
                    default=DEFAULT_CACHE_TTL_MINUTES,
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(
                    CONF_SYSTEM_PROMPT,
                    default=DEFAULT_SYSTEM_PROMPT,
                ): cv.string,
                vol.Required(CONF_TOPICS): vol.All(cv.ensure_list, [TOPIC_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SPEAKER_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ELEVENLABS_VOICE_ID): cv.string,
        vol.Required(ATTR_ELEVENLABS_MODEL): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Morning Brief integration."""
    hass.data.setdefault(DOMAIN, {})

    cache_dir = Path(tempfile.gettempdir()) / DOMAIN
    cache_dir.mkdir(parents=True, exist_ok=True)
    hass.data[DOMAIN][DATA_CACHE_DIR] = cache_dir

    if not hass.data[DOMAIN].get(DATA_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/api/{DOMAIN}/cache", str(cache_dir), False)]
        )
        hass.data[DOMAIN][DATA_STATIC_REGISTERED] = True

    if not hass.data[DOMAIN].get(DATA_SERVICE_REGISTERED):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE,
            _async_handle_generate_service,
            schema=SERVICE_SCHEMA,
        )
        hass.data[DOMAIN][DATA_SERVICE_REGISTERED] = True

    if DOMAIN in config and not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Morning Brief from a config entry."""
    config = dict(entry.data)
    config.update(entry.options)

    cache_manager = CacheManager(hass, hass.data[DOMAIN][DATA_CACHE_DIR])
    await cache_manager.async_prepare()

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(DEFAULT_HTTP_TIMEOUT_SECONDS),
        follow_redirects=True,
    )
    coordinator = MorningBriefCoordinator(
        hass,
        config=config,
        cache_manager=cache_manager,
        rss_fetcher=RSSFetcher(http_client),
        llm_client=ZAIClient(
            api_key=config[CONF_ZAI_API_KEY],
            base_url=config[CONF_ZAI_BASE_URL],
            model=config[CONF_ZAI_MODEL],
        ),
        tts_client=ElevenLabsTTSClient(config[CONF_ELEVENLABS_API_KEY]),
        media_controller=MediaController(hass),
        http_client=http_client,
    )

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Morning Brief config entry."""
    coordinator: MorningBriefCoordinator | None = entry.runtime_data
    if coordinator is not None:
        await coordinator.http_client.aclose()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_generate_service(call: ServiceCall) -> None:
    """Handle the morning_brief.generate service."""
    hass = call.hass
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        _LOGGER.error("The Morning Brief service was called before the integration was configured")
        raise HomeAssistantError("Morning Brief is not configured")

    entry = entries[0]
    coordinator: MorningBriefCoordinator | None = entry.runtime_data
    if coordinator is None:
        _LOGGER.error("The Morning Brief config entry is not ready yet")
        raise HomeAssistantError("Morning Brief is not ready yet")

    try:
        await coordinator.async_generate_and_play(
            speaker_entity_id=call.data[ATTR_SPEAKER_ENTITY_ID],
            elevenlabs_voice_id=call.data[ATTR_ELEVENLABS_VOICE_ID],
            elevenlabs_model=call.data[ATTR_ELEVENLABS_MODEL],
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Morning Brief generation failed: %s", err)
        raise HomeAssistantError(str(err)) from err
