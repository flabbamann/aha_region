"""Test AhaApi."""

import asyncio
from datetime import date, datetime, timedelta
import sys

import aiohttp
import pytest

from custom_components.aha_region.coordinator import AhaApi

# aiodns needs a SelectorEventLoop on Windows.
# See https://github.com/saghul/aiodns/issues/86
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
                <= datetime.strptime(
                    response[wastetype][0].split()[1], "%d.%m.%Y"
                ).date()
                < date.today() + timedelta(weeks=4)
            )
