"""aha custom component."""

from dataclasses import dataclass

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from .const import (
    CONF_ABHOLPLATZ,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
    DOMAIN,
)
from .coordinator import AhaApi, AhaUpdateCoordinator


@dataclass
class AhaRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: AhaUpdateCoordinator
    base_id: str


# Home Assistant integrations commonly expose this constant in upper-case.
# pylint: disable=invalid-name
CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the aha component."""
    del hass, config
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up aha_region from a config entry."""
    session = async_get_clientsession(hass)

    strasse = str(entry.data.get(CONF_STRASSE, ""))
    hausnr = int(entry.data.get(CONF_HAUSNR, 0))
    hausnraddon = str(entry.data.get(CONF_HAUSNRADDON, ""))
    abholplatz = str(entry.data.get(CONF_ABHOLPLATZ, ""))

    api = AhaApi(
        session,
        str(entry.data.get(CONF_GEMEINDE, "")),
        strasse,
        hausnr,
        hausnraddon,
        abholplatz,
    )
    coordinator = AhaUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.data is None:
        raise ConfigEntryNotReady("Could not get data from aha website")

    base_id = slugify(strasse + str(hausnr) + hausnraddon + abholplatz)
    entry.runtime_data = AhaRuntimeData(coordinator=coordinator, base_id=base_id)

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an aha_region config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unloaded:
        entry.runtime_data = None
    return unloaded
