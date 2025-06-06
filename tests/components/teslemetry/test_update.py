"""Test the Teslemetry update platform."""

import copy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.update import INSTALLING
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


async def test_update(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_services(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update services work."""

    await setup_platform(hass, [Platform.UPDATE])

    entity_id = "update.test_update"

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.schedule_software_update",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        call.assert_called_once()

    VEHICLE_INSTALLING = copy.deepcopy(VEHICLE_DATA)
    VEHICLE_INSTALLING["response"]["vehicle_state"]["software_update"]["status"] = (
        INSTALLING
    )
    mock_vehicle_data.return_value = VEHICLE_INSTALLING
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["in_progress"] == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the select entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 50,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state == snapshot(name="downloading")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 1,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state == snapshot(name="ready")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 50,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state == snapshot(name="installing")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "",
                Signal.VERSION: "2025.2.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state == snapshot(name="updated")

    await reload_platform(hass, entry, [Platform.UPDATE])

    state = hass.states.get("update.test_update")
    assert state == snapshot(name="restored")
