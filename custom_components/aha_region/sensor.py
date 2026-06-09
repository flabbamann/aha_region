"""aha sensor platform."""

from collections.abc import Callable, Mapping

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
import voluptuous as vol

from . import AhaRuntimeData
from .const import (
    CONF_ABHOLPLATZ,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
    DOMAIN,
)
from .coordinator import AhaApi, AhaUpdateCoordinator

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_GEMEINDE): cv.string,
        vol.Required(CONF_HAUSNR): cv.positive_int,
        vol.Required(CONF_STRASSE): cv.string,
        vol.Optional(CONF_HAUSNRADDON): cv.string,
        vol.Optional(CONF_ABHOLPLATZ): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    del discovery_info
    await _async_setup_entities(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    del hass
    runtime_data: AhaRuntimeData = entry.runtime_data
    if runtime_data.coordinator.data is None:
        raise PlatformNotReady("Could not get data from aha website")

    async_add_entities(
        AhaWasteSensor(
            runtime_data.coordinator,
            wastetype,
            runtime_data.base_id,
            entry.title,
        )
        for wastetype in runtime_data.coordinator.data
    )


async def _async_setup_entities(
    hass: HomeAssistant,
    config: Mapping[str, object],
    async_add_entities: AddEntitiesCallback | Callable,
) -> None:
    """Create waste sensors from a config mapping."""
    session = async_get_clientsession(hass)

    strasse = str(config.get(CONF_STRASSE))
    hausnr_value = config.get(CONF_HAUSNR)
    if not isinstance(hausnr_value, int):
        raise PlatformNotReady("Invalid house number configuration")
    hausnr = hausnr_value
    hausnraddon = str(config.get(CONF_HAUSNRADDON) or "")
    abholplatz = str(config.get(CONF_ABHOLPLATZ) or "")

    api = AhaApi(
        session,
        str(config.get(CONF_GEMEINDE)),
        strasse,
        hausnr,
        hausnraddon,
        abholplatz,
    )

    baseid = slugify(strasse + str(hausnr) + hausnraddon + abholplatz)

    coordinator = AhaUpdateCoordinator(hass, api)

    await coordinator.async_refresh()

    if coordinator.data is None:
        raise PlatformNotReady("Could not get data from aha website")

    device_name = f"aha region {str(config.get(CONF_GEMEINDE))}"
    async_add_entities(
        AhaWasteSensor(coordinator, wastetype, baseid, device_name)
        for wastetype in coordinator.data
    )


class AhaWasteSensor(CoordinatorEntity, SensorEntity):
    """aha waste sensor."""

    def __init__(
        self,
        coordinator: AhaUpdateCoordinator,
        wastetype: str,
        baseid: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name: str = wastetype
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_unique_id = f"{baseid}_{wastetype}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, baseid)},
            name=device_name,
            manufacturer="aha region",
        )
        self._attr_native_value = self._get_native_value()

    def _get_native_value(self):
        """Return the next collection date for the entity type."""
        dates = self.coordinator.data.get(self._attr_name, [])
        return dates[0] if dates else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._get_native_value()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()
