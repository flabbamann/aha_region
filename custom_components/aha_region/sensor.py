"""aha sensor platform."""
from collections.abc import Callable
from typing import Optional

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import voluptuous as vol

from .const import (
    ABFALLARTEN,
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

    api = AhaApi(
        session,
        str(config.get(CONF_GEMEINDE)),
        str(config.get(CONF_STRASSE)),
        int(config[CONF_HAUSNR]),
        str(config.get(CONF_HAUSNRADDON) or ""),
    )

    coordinator = AhaUpdateCoordinator(hass, api)

    await coordinator.async_refresh()

    async_add_entities(
        AhaWasteSensor(coordinator, wastetype) for wastetype in ABFALLARTEN
    )


class AhaWasteSensor(CoordinatorEntity, SensorEntity):
    """aha waste sensor."""

    def __init__(self, coordinator: AhaUpdateCoordinator, wastetype: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = wastetype
        self._attr_name = wastetype
        self._attr_device_class = SensorDeviceClass.DATE
        self._state = None
        self._available = True
        self._attr_native_value = self.coordinator.data[self._name]

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self._name]
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()
