"""Test AhaApi."""

from datetime import date, datetime, timedelta

import aiohttp
import pytest

from custom_components.aha_region.coordinator import AhaApi

GEMEINDE = "Hannover"
STRASSE = "00826@Engelbosteler Damm / Nordstadt@Nordstadt"
HAUSNR = 11
HAUSNRADDON = ""


@pytest.mark.asyncio
async def test_aha_api():
    """This test will fail if aha website is changed (or down...)."""
    async with aiohttp.ClientSession(
        # without foce_close a "RuntimeError: Event loop is closed" is raised
        # ssl verification fails in the test (certificate expired). no idea why...
        connector=aiohttp.TCPConnector(force_close=True, ssl=False)
    ) as session:
        api = AhaApi(session, GEMEINDE, STRASSE, HAUSNR, HAUSNRADDON, "")
        response = await api.get_data()
        assert len(response) == 4
        for wastetype in response:
            assert (
                date.today()
                <= datetime.strptime(response[wastetype].split()[1], "%d.%m.%Y").date()
                < date.today() + timedelta(weeks=4)
            )
