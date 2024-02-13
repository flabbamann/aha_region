"""aha sensor platform."""

from collections.abc import Callable
from typing import Optional

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CONF_ABHOLPLATZ,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
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
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensor platform."""
    session = async_get_clientsession(hass)

    strasse = str(config.get(CONF_STRASSE))
    hausnr = int(config.get(CONF_HAUSNR))
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

    async_add_entities(
        AhaWasteSensor(coordinator, wastetype, baseid) for wastetype in coordinator.data
    )


class AhaWasteSensor(CoordinatorEntity, SensorEntity):
    """aha waste sensor."""

    def __init__(
        self, coordinator: AhaUpdateCoordinator, wastetype: str, baseid: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = wastetype
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_unique_id = f"{baseid}_{wastetype}"
        self._state = None

        self._available = True
        self._attr_native_value = self.coordinator.data[self._attr_name]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self._attr_name]
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()
