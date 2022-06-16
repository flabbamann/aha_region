"""aha sensor platform"""
from datetime import datetime, timedelta
import logging
import re
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
import voluptuous as vol

from .const import (
    ABFALLARTEN,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

URL = "https://www.aha-region.de/abholtermine/abfuhrkalender"
DATE_RE = re.compile(r"\w{2}, (\d{2}\.\d{2}\.\d{4})")

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
        config.get(CONF_GEMEINDE),
        config.get(CONF_STRASSE),
        config.get(CONF_HAUSNR),
        config.get(CONF_HAUSNRADDON),
    )
    resp = await api.get_data()
    sensors = []
    for wastetype in ABFALLARTEN:
        hass.data[DOMAIN][wastetype] = datetime.strptime(
            resp[wastetype].split()[1], "%d.%m.%Y"
        ).date()
        sensors.append(AhaWasteSensor(wastetype))

    async_add_entities(sensors, update_before_add=True)


class AhaWasteSensor(SensorEntity):
    """aha waste sensor"""

    def __init__(self, wastetype: str) -> None:
        super().__init__()
        self._name = wastetype
        self._attr_name = wastetype
        self._attr_device_class = SensorDeviceClass.DATE
        self._state = None
        self._available = True
        self._attr_native_value = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._attr_native_value = self.hass.data[DOMAIN][self._name]


class AhaApi:
    """wrapper class for requests"""

    def __init__(self, session, gemeinde, strasse, hausnr, hausnraddon) -> None:
        """Initialize."""
        self.session = session
        self._gemeinde = gemeinde
        self._strasse = strasse
        self._hausnr = hausnr
        self._hausnraddon = hausnraddon

    async def get_data(self) -> dict[str, str]:
        """Get data from aha website"""
        value = {}
        request = {
            "gemeinde": self._gemeinde,
            "strasse": self._strasse,
            "hausnr": str(self._hausnr),
            "hausnraddon": str(self._hausnraddon or ""),
        }
        # _LOGGER.info(request)
        response = await self.session.post(URL, data=request)
        # _LOGGER.info(response)
        soup = BeautifulSoup(await response.text(), "html.parser")
        table = soup.find_all("table")[0]
        # _LOGGER.info(table)
        for abfallart in ABFALLARTEN:
            abf = table.find(string=abfallart)
            termine = (
                abf.find_parent("tr").find_next_sibling("tr").find_all(string=DATE_RE)
            )
            value[abfallart] = termine[0]

        _LOGGER.info(value)

        return value
