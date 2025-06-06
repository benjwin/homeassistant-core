"""Button platform for Sensibo integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SensiboConfigEntry
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SensiboButtonEntityDescription(ButtonEntityDescription):
    """Class describing Sensibo Button entities."""

    data_key: str


DEVICE_BUTTON_TYPES = SensiboButtonEntityDescription(
    key="reset_filter",
    translation_key="reset_filter",
    entity_category=EntityCategory.CONFIG,
    data_key="filter_clean",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sensibo button platform."""

    coordinator = entry.runtime_data

    added_devices: set[str] = set()

    def _add_remove_devices() -> None:
        """Handle additions of devices and sensors."""
        nonlocal added_devices
        new_devices, _, new_added_devices = coordinator.get_devices(added_devices)
        added_devices = new_added_devices

        if new_devices:
            async_add_entities(
                SensiboDeviceButton(coordinator, device_id, DEVICE_BUTTON_TYPES)
                for device_id in coordinator.data.parsed
                if device_id in new_devices
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_remove_devices))
    _add_remove_devices()


class SensiboDeviceButton(SensiboDeviceBaseEntity, ButtonEntity):
    """Representation of a Sensibo Device button."""

    entity_description: SensiboButtonEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboButtonEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Button."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.async_send_api_call(
            key=self.entity_description.data_key,
            value=False,
        )

    @async_handle_api_call
    async def async_send_api_call(self, key: str, value: Any) -> bool:
        """Make service call to api."""
        result = await self._client.async_reset_filter(
            self._device_id,
        )
        return bool(result.get("status") == "success")
