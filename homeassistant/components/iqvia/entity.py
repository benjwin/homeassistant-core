"""Support for IQVIA."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ZIP_CODE, TYPE_ALLERGY_FORECAST, TYPE_ALLERGY_OUTLOOK
from .coordinator import IqviaConfigEntry, IqviaUpdateCoordinator


class IQVIAEntity(CoordinatorEntity[IqviaUpdateCoordinator]):
    """Define a base IQVIA entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IqviaUpdateCoordinator,
        entry: IqviaConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{entry.data[CONF_ZIP_CODE]}_{description.key}"
        self._entry = entry
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            return

        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self.entity_description.key == TYPE_ALLERGY_FORECAST:
            self.async_on_remove(
                self._entry.runtime_data[TYPE_ALLERGY_OUTLOOK].async_add_listener(
                    self._handle_coordinator_update
                )
            )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
