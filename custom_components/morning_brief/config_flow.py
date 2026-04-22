"""Config flow for Morning Brief."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
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
    DEFAULT_CACHE_ENABLED,
    DEFAULT_CACHE_TTL_MINUTES,
    DEFAULT_RSS_LOOKBACK_DAYS,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_ZAI_BASE_URL,
    DEFAULT_ZAI_MODEL,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class MorningBriefConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Morning Brief."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._config: dict[str, Any] = _default_config()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MorningBriefOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial setup flow."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._config.update(_normalize_globals(user_input))
            except ValueError:
                errors["base"] = "invalid_input"
            else:
                return await self.async_step_add_topic()

        return self.async_show_form(
            step_id="user",
            data_schema=_build_globals_schema(self._config),
            errors=errors,
        )

    async def async_step_add_topic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Add a topic during initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                topic = _normalize_topic_input(user_input)
            except ValueError:
                errors["base"] = "invalid_feeds"
            else:
                self._config[CONF_TOPICS].append(topic)
                return await self.async_step_topic_menu()

        return self.async_show_form(
            step_id="add_topic",
            data_schema=_build_topic_schema(),
            errors=errors,
        )

    async def async_step_topic_menu(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Offer topic actions after at least one topic is added."""
        menu_options = ["add_topic"]
        if self._config[CONF_TOPICS]:
            menu_options.append("finish")

        return self.async_show_menu(
            step_id="topic_menu",
            menu_options=menu_options,
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Finish setup."""
        if not self._config[CONF_TOPICS]:
            return self.async_abort(reason="no_topics")

        return self.async_create_entry(title=NAME, data=self._config)

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import configuration from configuration.yaml."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        try:
            config = _normalize_full_config(import_data)
        except ValueError:
            _LOGGER.error("Invalid configuration.yaml data for %s", DOMAIN)
            return self.async_abort(reason="invalid_import")

        return self.async_create_entry(title=NAME, data=config)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to reconfigure required integration data."""
        entry = self._get_reconfigure_entry()
        current = _merge_entry_config(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data_updates = _normalize_globals(user_input)
            except ValueError:
                errors["base"] = "invalid_input"
            else:
                if entry.unique_id is not None:
                    await self.async_set_unique_id(entry.unique_id)
                    self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_globals_schema(current),
            errors=errors,
        )


class MorningBriefOptionsFlow(OptionsFlow):
    """Manage Morning Brief options."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        super().__init__()
        self._config: dict[str, Any] | None = None
        self._selected_topic_index: int | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show the options menu."""
        if self._config is None:
            self._config = _merge_entry_config(self.config_entry)

        menu_options = ["edit_globals", "add_topic"]
        if self._config[CONF_TOPICS]:
            menu_options.extend(["edit_topic_select", "delete_topic"])
        menu_options.append("save")

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_edit_globals(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Edit global options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._config.update(_normalize_globals(user_input))
            except ValueError:
                errors["base"] = "invalid_input"
            else:
                return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_globals",
            data_schema=_build_globals_schema(self._config),
            errors=errors,
        )

    async def async_step_add_topic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Add a topic."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._config[CONF_TOPICS].append(_normalize_topic_input(user_input))
            except ValueError:
                errors["base"] = "invalid_feeds"
            else:
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_topic",
            data_schema=_build_topic_schema(),
            errors=errors,
        )

    async def async_step_edit_topic_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose which topic to edit."""
        if not self._config[CONF_TOPICS]:
            return self.async_abort(reason="no_topics")

        topic_choices = _topic_choice_map(self._config[CONF_TOPICS])
        if user_input is not None:
            self._selected_topic_index = int(user_input["selected_topic"])
            return await self.async_step_edit_topic()

        return self.async_show_form(
            step_id="edit_topic_select",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_topic"): vol.In(topic_choices),
                }
            ),
        )

    async def async_step_edit_topic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Edit the selected topic."""
        if self._selected_topic_index is None:
            return await self.async_step_edit_topic_select()

        errors: dict[str, str] = {}
        current = self._config[CONF_TOPICS][self._selected_topic_index]

        if user_input is not None:
            try:
                self._config[CONF_TOPICS][self._selected_topic_index] = _normalize_topic_input(
                    user_input
                )
            except ValueError:
                errors["base"] = "invalid_feeds"
            else:
                self._selected_topic_index = None
                return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_topic",
            data_schema=_build_topic_schema(current),
            errors=errors,
        )

    async def async_step_delete_topic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Delete a topic."""
        if not self._config[CONF_TOPICS]:
            return self.async_abort(reason="no_topics")

        topic_choices = _topic_choice_map(self._config[CONF_TOPICS])
        if user_input is not None:
            topic_index = int(user_input["selected_topic"])
            self._config[CONF_TOPICS].pop(topic_index)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_topic",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_topic"): vol.In(topic_choices),
                }
            ),
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Persist all edited options."""
        return self.async_create_entry(data=self._config)


def _default_config() -> dict[str, Any]:
    """Return the default config structure."""
    return {
        CONF_ZAI_API_KEY: "",
        CONF_ZAI_BASE_URL: DEFAULT_ZAI_BASE_URL,
        CONF_ZAI_MODEL: DEFAULT_ZAI_MODEL,
        CONF_ELEVENLABS_API_KEY: "",
        CONF_RSS_LOOKBACK_DAYS: DEFAULT_RSS_LOOKBACK_DAYS,
        CONF_CACHE_ENABLED: DEFAULT_CACHE_ENABLED,
        CONF_CACHE_TTL_MINUTES: DEFAULT_CACHE_TTL_MINUTES,
        CONF_SYSTEM_PROMPT: DEFAULT_SYSTEM_PROMPT,
        CONF_TOPICS: [],
    }


def _merge_entry_config(config_entry: ConfigEntry) -> dict[str, Any]:
    """Merge entry data and options."""
    merged = dict(config_entry.data)
    merged.update(dict(config_entry.options))
    merged.setdefault(CONF_TOPICS, [])
    return merged


def _build_globals_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the schema for global settings."""
    return vol.Schema(
        {
            vol.Required(CONF_ZAI_API_KEY, default=current.get(CONF_ZAI_API_KEY, "")): str,
            vol.Required(
                CONF_ZAI_BASE_URL,
                default=current.get(CONF_ZAI_BASE_URL, DEFAULT_ZAI_BASE_URL),
            ): str,
            vol.Required(
                CONF_ZAI_MODEL,
                default=current.get(CONF_ZAI_MODEL, DEFAULT_ZAI_MODEL),
            ): str,
            vol.Required(
                CONF_ELEVENLABS_API_KEY,
                default=current.get(CONF_ELEVENLABS_API_KEY, ""),
            ): str,
            vol.Required(
                CONF_RSS_LOOKBACK_DAYS,
                default=current.get(CONF_RSS_LOOKBACK_DAYS, DEFAULT_RSS_LOOKBACK_DAYS),
            ): vol.All(int, vol.Range(min=1, max=30)),
            vol.Required(
                CONF_CACHE_ENABLED,
                default=current.get(CONF_CACHE_ENABLED, DEFAULT_CACHE_ENABLED),
            ): bool,
            vol.Required(
                CONF_CACHE_TTL_MINUTES,
                default=current.get(CONF_CACHE_TTL_MINUTES, DEFAULT_CACHE_TTL_MINUTES),
            ): vol.All(int, vol.Range(min=1, max=1440)),
            vol.Required(
                CONF_SYSTEM_PROMPT,
                default=current.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
            ): str,
        }
    )


def _build_topic_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build the schema for a topic."""
    current = current or {}
    return vol.Schema(
        {
            vol.Required(CONF_TOPIC_NAME, default=current.get(CONF_TOPIC_NAME, "")): str,
            vol.Required(
                CONF_TOPIC_PROMPT,
                default=current.get(CONF_TOPIC_PROMPT, ""),
            ): str,
            vol.Required(
                CONF_TOPIC_FEEDS,
                default="\n".join(current.get(CONF_TOPIC_FEEDS, [])),
            ): str,
        }
    )


def _normalize_globals(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize the global settings."""
    base_url = str(values.get(CONF_ZAI_BASE_URL, DEFAULT_ZAI_BASE_URL)).strip().rstrip("/")
    if not _is_valid_url(base_url):
        raise ValueError("Invalid base URL")

    return {
        CONF_ZAI_API_KEY: str(values.get(CONF_ZAI_API_KEY, "")).strip(),
        CONF_ZAI_BASE_URL: base_url,
        CONF_ZAI_MODEL: str(values.get(CONF_ZAI_MODEL, DEFAULT_ZAI_MODEL)).strip(),
        CONF_ELEVENLABS_API_KEY: str(values.get(CONF_ELEVENLABS_API_KEY, "")).strip(),
        CONF_RSS_LOOKBACK_DAYS: int(
            values.get(CONF_RSS_LOOKBACK_DAYS, DEFAULT_RSS_LOOKBACK_DAYS)
        ),
        CONF_CACHE_ENABLED: bool(values.get(CONF_CACHE_ENABLED, DEFAULT_CACHE_ENABLED)),
        CONF_CACHE_TTL_MINUTES: int(
            values.get(CONF_CACHE_TTL_MINUTES, DEFAULT_CACHE_TTL_MINUTES)
        ),
        CONF_SYSTEM_PROMPT: str(
            values.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
        ).strip(),
    }


def _normalize_topic_input(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize a topic from UI input."""
    feeds = _parse_feeds(values[CONF_TOPIC_FEEDS])
    if not feeds:
        raise ValueError("At least one valid feed is required")

    return {
        CONF_TOPIC_NAME: values[CONF_TOPIC_NAME].strip(),
        CONF_TOPIC_PROMPT: values[CONF_TOPIC_PROMPT].strip(),
        CONF_TOPIC_FEEDS: feeds,
    }


def _normalize_full_config(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize a full config payload, such as a YAML import."""
    normalized = _normalize_globals(values)
    topics = []
    for topic in values.get(CONF_TOPICS, []):
        feeds = topic.get(CONF_TOPIC_FEEDS, [])
        topics.append(
            {
                CONF_TOPIC_NAME: str(topic[CONF_TOPIC_NAME]).strip(),
                CONF_TOPIC_PROMPT: str(topic[CONF_TOPIC_PROMPT]).strip(),
                CONF_TOPIC_FEEDS: [feed.strip() for feed in feeds if _is_valid_url(feed.strip())],
            }
        )

    if not topics or any(not topic[CONF_TOPIC_FEEDS] for topic in topics):
        raise ValueError("Invalid topics")

    normalized[CONF_TOPICS] = topics
    return normalized


def _parse_feeds(raw_value: str) -> list[str]:
    """Parse newline or comma separated feeds."""
    parts = []
    for chunk in raw_value.replace(",", "\n").splitlines():
        feed = chunk.strip()
        if feed and _is_valid_url(feed):
            parts.append(feed)
    return parts


def _topic_choice_map(topics: list[dict[str, Any]]) -> dict[str, str]:
    """Build a display map for topic selection."""
    return {str(index): topic[CONF_TOPIC_NAME] for index, topic in enumerate(topics)}


def _is_valid_url(value: str) -> bool:
    """Return whether a URL looks valid enough for the flow."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
