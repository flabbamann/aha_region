"""update coordinator for aha custom component"""
import re
import async_timeout
from bs4 import BeautifulSoup

from .const import ABFALLARTEN, LOGGER, URL
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant

from datetime import date, datetime, timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

DATE_RE = re.compile(r"\w{2}, (\d{2}\.\d{2}\.\d{4})")


class AhaApi:
    """wrapper class for requests"""

    def __init__(
        self,
        session: ClientSession,
        gemeinde: str,
        strasse: str,
        hausnr: int,
        hausnraddon: str,
    ) -> None:
        """Initialize."""
        self.session = session
        self._gemeinde = gemeinde
        self._strasse = strasse.replace(" ", "+")
        self._hausnr = hausnr
        self._hausnraddon = hausnraddon

    async def get_data(self) -> dict[str, str]:
        """Get data from aha website"""
        value = {}
        request = {
            "gemeinde": self._gemeinde,
            "strasse": self._strasse,
            "hausnr": str(self._hausnr),
            "hausnraddon": self._hausnraddon,
        }
        LOGGER.debug("Request data: %s", request)
        response = await self.session.post(URL, data=request)
        LOGGER.debug("Response: %s", response)
        soup = BeautifulSoup(await response.text(), "html.parser")
        table = soup.find_all("table")[0]
        for wastetype in ABFALLARTEN:
            abf = table.find(string=wastetype)
            termine = (
                abf.find_parent("tr").find_next_sibling("tr").find_all(string=DATE_RE)
            )
            value[wastetype] = termine[0]

        LOGGER.info(value)

        return value


class AhaUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, my_api: AhaApi) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name="aha Region",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
        )
        self.my_api = my_api

    async def _async_update_data(self) -> dict[str, date]:
        """Fetch data from API endpoint."""
        async with async_timeout.timeout(10):
            LOGGER.debug("Start async_update_data()")
            response = await self.my_api.get_data()
            result = {}
            for wastetype in ABFALLARTEN:
                result[wastetype] = datetime.strptime(
                    response[wastetype].split()[1], "%d.%m.%Y"
                ).date()
            LOGGER.debug(result)
            return result
