"""aha custom component."""

from dataclasses import dataclass

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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


def _legacy_yaml_configs(config: dict) -> list[dict]:
    """Return YAML sensor configurations that should be imported."""
    if not isinstance(config, dict):
        return []

    entries: list[dict] = []
    for platform_config in config.get("sensor", []):
        if not isinstance(platform_config, dict):
            continue
        if platform_config.get("platform") != DOMAIN:
            continue
        yaml_data = dict(platform_config)
        yaml_data.pop("platform", None)
        entries.append(yaml_data)
    return entries


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the aha component."""
    yaml_configs = _legacy_yaml_configs(config)

    if yaml_configs:
        for yaml_config in yaml_configs:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=yaml_config,
                )
            )

        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_config_removal",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_config_removal",
        )
        return True

    ir.async_delete_issue(hass, DOMAIN, "yaml_config_removal")
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
