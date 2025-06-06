"""Mock inputs for tests."""

from pylamarzocco.const import ModelName

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

HOST_SELECTION = {
    CONF_HOST: "192.168.1.1",
}

PASSWORD_SELECTION = {
    CONF_PASSWORD: "password",
}

USER_INPUT = PASSWORD_SELECTION | {CONF_USERNAME: "username"}

SERIAL_DICT = {
    ModelName.GS3_AV: "GS012345",
    ModelName.GS3_MP: "GS012345",
    ModelName.LINEA_MICRA: "MR012345",
    ModelName.LINEA_MINI: "LM012345",
}

WAKE_UP_SLEEP_ENTRY_IDS = ["Os2OswX", "aXFz5bJ"]


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the La Marzocco integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def get_bluetooth_service_info(model: ModelName, serial: str) -> BluetoothServiceInfo:
    """Return a mocked BluetoothServiceInfo."""
    if model in (ModelName.GS3_AV, ModelName.GS3_MP):
        name = f"GS3_{serial}"
    elif model == ModelName.LINEA_MINI:
        name = f"MINI_{serial}"
    elif model == ModelName.LINEA_MICRA:
        name = f"MICRA_{serial}"
    return BluetoothServiceInfo(
        name=name,
        address="aa:bb:cc:dd:ee:ff",
        rssi=-63,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
    )
