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
STREET_INITIAL_RE = re.compile(r"submitFormWithExtraValue\('([^']+)'\)")


class AhaApi:
    """wrapper class for requests."""

    # Data fields mirror the remote form payload and are passed explicitly.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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

    async def _fetch_soup(
        self, request_data: dict[str, str] | None = None
    ) -> BeautifulSoup:
        """Fetch the calendar page and return the parsed HTML."""
        timeout = ClientTimeout(total=30)
        LOGGER.debug("Timeout: %s", timeout)
        LOGGER.debug("Request data: %s", request_data)
        response = await self.session.post(URL, data=request_data, timeout=timeout)
        LOGGER.debug("Response: %s", response)
        response_text = await response.text()
        LOGGER.debug("Response length: %s", len(response_text))
        return BeautifulSoup(response_text, "html.parser")

    @staticmethod
    def _parse_select_options(soup: BeautifulSoup, field_name: str) -> dict[str, str]:
        """Extract non-empty options from a select field."""
        select = soup.find("select", attrs={"name": field_name})
        if select is None:
            return {}

        options: dict[str, str] = {}
        for option in select.find_all("option"):
            value = option.get("value")
            label = option.get_text(strip=True)
            if not value or not label:
                continue
            options[label] = value

        return options

    async def get_gemeinden(self) -> dict[str, str]:
        """Fetch available municipalities."""
        soup = await self._fetch_soup()
        return self._parse_select_options(soup, "gemeinde")

    async def get_street_initials(self, gemeinde: str) -> dict[str, str]:
        """Fetch available street initials for a municipality."""
        soup = await self._fetch_soup({"gemeinde": gemeinde})
        initials: dict[str, str] = {}
        for anchor in soup.find_all("a", attrs={"onclick": True}):
            onclick = str(anchor.get("onclick"))
            match = STREET_INITIAL_RE.search(onclick)
            if not match:
                continue

            value = match.group(1).strip()
            if not value:
                continue

            label = anchor.get_text(strip=True) or value
            initials[label] = value

        return initials

    async def get_strassen(self, gemeinde: str, von: str) -> dict[str, str]:
        """Fetch available streets for a municipality."""
        soup = await self._fetch_soup({"gemeinde": gemeinde, "von": von})
        return self._parse_select_options(soup, "strasse")

    async def get_ladeorte(
        self,
        gemeinde: str,
        strasse: str,
        hausnr: int,
        hausnraddon: str,
    ) -> dict[str, str]:
        """Fetch available pickup places for an address."""
        soup = await self._fetch_soup(
            {
                "gemeinde": gemeinde,
                "strasse": strasse,
                "hausnr": str(hausnr),
                "hausnraddon": hausnraddon,
            }
        )
        return self._parse_select_options(soup, "ladeort")

    async def get_data(self) -> dict[str, list[str]]:
        """Get data from aha website."""
        data = {}
        request = {
            "gemeinde": self._gemeinde,
            "strasse": self._strasse,
            "hausnr": str(self._hausnr),
            "hausnraddon": self._hausnraddon,
            "ladeort": self._ladeort,
        }
        soup = await self._fetch_soup(request)
        tables = soup.find_all("table")
        if not tables:
            LOGGER.info("No data table found for the given address")
            return data

        table = tables[0]
        for wastetype in ABFALLARTEN:
            try:
                abf = table.find(string=wastetype)
                data[wastetype] = [
                    str(date_str)
                    # Ignore types, we catch AttributeError below
                    for date_str in abf.find_parent("tr")  # type: ignore
                    .find_next_sibling("tr")  # type: ignore
                    .find_all(string=DATE_RE)  # type: ignore
                ]
            except AttributeError:
                LOGGER.info("Wastetype %s not found for given address", wastetype)

        LOGGER.info("Refresh successful, next dates: %s", data)
        return data


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

    async def _async_update_data(self) -> dict[str, list[date]]:
        """Fetch data from API."""
        async with asyncio.timeout(30):
            LOGGER.debug("Start async_update_data()")
            response = await self.api.get_data()
            result = {}
            for wastetype in response:
                date_strings = response[wastetype]
                result[wastetype] = [
                    datetime.strptime(s.split()[1], "%d.%m.%Y").date()
                    for s in date_strings
                ]
            LOGGER.debug(result)
            return result
