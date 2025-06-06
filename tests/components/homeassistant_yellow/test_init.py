"""Test the Home Assistant Yellow integration."""

from unittest.mock import patch

import pytest

from homeassistant.components import zha
from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.homeassistant_yellow.config_flow import (
    HomeAssistantYellowConfigFlow,
)
from homeassistant.components.homeassistant_yellow.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.mark.parametrize(
    ("onboarded", "num_entries", "num_flows"), [(False, 1, 0), (True, 0, 1)]
)
async def test_setup_entry(
    hass: HomeAssistant, onboarded, num_entries, num_flows, addon_store_info
) -> None:
    """Test setup of a config entry, including setup of zha."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=onboarded,
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.guess_firmware_info",
            return_value=FirmwareInfo(  # Nothing is setup
                device="/dev/ttyAMA1",
                firmware_version=None,
                firmware_type=ApplicationType.EZSP,
                source="unknown",
                owners=[],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    if num_entries > 0:
        zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
        assert len(zha_flows) == 1
        assert zha_flows[0]["step_id"] == "choose_formation_strategy"

        await hass.config_entries.flow.async_configure(
            zha_flows[0]["flow_id"],
            user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress_by_handler("zha")) == num_flows
    assert len(hass.config_entries.async_entries("zha")) == num_entries

    # Test unloading the config entry
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_setup_zha(hass: HomeAssistant, addon_store_info) -> None:
    """Test zha gets the right config."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
    assert len(zha_flows) == 1
    assert zha_flows[0]["step_id"] == "choose_formation_strategy"

    await hass.config_entries.flow.async_configure(
        zha_flows[0]["flow_id"],
        user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {
            "baudrate": 115200,
            "flow_control": "hardware",
            "path": "/dev/ttyAMA1",
        },
        "radio_type": "ezsp",
    }
    assert config_entry.options == {}
    assert config_entry.title == "Yellow"


async def test_setup_entry_no_hassio(hass: HomeAssistant) -> None:
    """Test setup of a config entry without hassio."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries()) == 1

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info"
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 0
    assert len(hass.config_entries.async_entries()) == 0


async def test_setup_entry_wrong_board(hass: HomeAssistant) -> None:
    """Test setup of a config entry with wrong board type."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries()) == 1

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value={"board": "generic-x86-64"},
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 1
    assert len(hass.config_entries.async_entries()) == 0


async def test_setup_entry_wait_hassio(hass: HomeAssistant) -> None:
    """Test setup of a config entry when hassio has not fetched os_info."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value=None,
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_addon_info_fails(
    hass: HomeAssistant, addon_store_info
) -> None:
    """Test setup of a config entry when fetching addon info fails."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.CPC},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.check_multi_pan_addon",
            side_effect=HomeAssistantError("Boom"),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("start_version", "data", "migrated_data"),
    [
        (1, {}, {"firmware": "ezsp", "firmware_version": None}),
        (2, {"firmware": "ezsp"}, {"firmware": "ezsp", "firmware_version": None}),
        (
            2,
            {"firmware": "ezsp", "firmware_version": "123"},
            {"firmware": "ezsp", "firmware_version": "123"},
        ),
        (3, {"firmware": "ezsp"}, {"firmware": "ezsp", "firmware_version": None}),
        (
            3,
            {"firmware": "ezsp", "firmware_version": "123"},
            {"firmware": "ezsp", "firmware_version": "123"},
        ),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    start_version: int,
    data: dict,
    migrated_data: dict,
) -> None:
    """Test migration of a config entry."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data=data,
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=start_version,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.guess_firmware_info",
            return_value=FirmwareInfo(  # Nothing is setup
                device="/dev/ttyAMA1",
                firmware_version="1234",
                firmware_type=ApplicationType.EZSP,
                source="unknown",
                owners=[],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.data == migrated_data
    assert config_entry.options == {}
    assert config_entry.minor_version == HomeAssistantYellowConfigFlow.MINOR_VERSION
    assert config_entry.version == HomeAssistantYellowConfigFlow.VERSION
