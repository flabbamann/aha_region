"""update coordinator for aha custom component."""

import asyncio
from datetime import date, datetime, timedelta
import re

from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ABFALLARTEN, LOGGER, URL

DATE_RE = re.compile(r"\w{2}, (\d{2}\.\d{2}\.\d{4})")


class AhaApi:
    """wrapper class for requests."""

    def __init__(
        self,
        session: ClientSession,
        gemeinde: str,
        strasse: str,
        hausnr: int,
        hausnraddon: str,
        ladeort: str,
    ) -> None:
        """Initialize."""
        self.session = session
        self._gemeinde = gemeinde
        self._strasse = strasse
        self._hausnr = hausnr
        self._hausnraddon = hausnraddon
        self._ladeort = ladeort

    async def get_data(self) -> dict[str, str]:
        """Get data from aha website."""
        value = {}
        request = {
            "gemeinde": self._gemeinde,
            "strasse": self._strasse,
            "hausnr": str(self._hausnr),
            "hausnraddon": self._hausnraddon,
            "ladeort": self._ladeort,
        }
        timeout = ClientTimeout(total=30)
        LOGGER.debug("Timeout: %s", timeout)
        LOGGER.debug("Request data: %s", request)
        response = await self.session.post(URL, data=request, timeout=timeout)
        LOGGER.debug("Response: %s", response)
        """log the length of the response"""
        LOGGER.debug("Response length: %s", len(await response.text()))
        soup = BeautifulSoup(await response.text(), "html.parser")
        table = soup.find_all("table")[0]
        for wastetype in ABFALLARTEN:
            try:
                abf = table.find(string=wastetype)
                dates = (
                    abf.find_parent("tr")
                    .find_next_sibling("tr")
                    .find_all(string=DATE_RE)
                )
                value[wastetype] = dates[0]
            except AttributeError:
                LOGGER.info("Wastetype %s not found for given address", wastetype)

        LOGGER.info("Refresh successful, next dates: %s", value)
        return value


class AhaUpdateCoordinator(DataUpdateCoordinator):
    """Aha Update coordinator."""

    def __init__(self, hass: HomeAssistant, api: AhaApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="aha Region",
            update_interval=timedelta(hours=3),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, date]:
        """Fetch data from API."""
        async with asyncio.timeout(30):
            LOGGER.debug("Start async_update_data()")
            response = await self.api.get_data()
            result = {}
            for wastetype in response:
                result[wastetype] = datetime.strptime(
                    response[wastetype].split()[1], "%d.%m.%Y"
                ).date()
            LOGGER.debug(result)
            return result
