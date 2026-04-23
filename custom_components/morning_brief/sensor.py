"""Sensor platform for Morning Brief."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME, SENSOR_LATEST_BRIEF_KEY, SENSOR_LATEST_BRIEF_NAME
from .coordinator import MorningBriefCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Morning Brief sensors."""
    coordinator: MorningBriefCoordinator = entry.runtime_data
    async_add_entities([MorningBriefLatestBriefSensor(coordinator, entry)])


class MorningBriefLatestBriefSensor(SensorEntity):
    """Expose the latest generated Morning Brief text."""

    _attr_icon = "mdi:text-box"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MorningBriefCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_LATEST_BRIEF_KEY}"
        self._attr_translation_key = SENSOR_LATEST_BRIEF_KEY
        self._attr_name = SENSOR_LATEST_BRIEF_NAME

    async def async_added_to_hass(self) -> None:
        """Register for coordinator updates."""
        remove_listener = self.coordinator.async_add_listener(self.async_write_ha_state)
        self.async_on_remove(remove_listener)

    @property
    def native_value(self) -> str:
        """Return a short preview of the latest generated brief."""
        if not self.coordinator.latest_brief:
            return "No brief generated yet"

        preview = " ".join(self.coordinator.latest_brief.split())
        if len(preview) > 250:
            return f"{preview[:247]}..."
        return preview

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full generated brief as attributes."""
        return {
            "full_text": self.coordinator.latest_brief,
            "generated_at": self.coordinator.latest_generated_at,
            "topic_summaries": self.coordinator.latest_topic_summaries,
        }

