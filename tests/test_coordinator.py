"""Tests for coordinator."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from custom_components.aha_region.coordinator import AhaApi

STREET_OPTION_VALUE = "00152@Am Küchengarten / " "Linden-Mitte@Linden-Mitte"
STREET_OPTION_LABEL = "Am Küchengarten / Linden-Mitte"

FORM_HTML = """
<html>
    <body>
        <a class="btn" onclick="submitFormWithExtraValue('A')">A</a>
        <a class="btn" onclick="submitFormWithExtraValue('D')">D</a>
        <select name="gemeinde" id="gemeinde">
            <option value="">Bitte wählen</option>
            <option value="Hannover">Hannover</option>
            <option value="Laatzen">Laatzen</option>
        </select>
        <select name="strasse" id="strasse">
            <option value="">Bitte wählen</option>
            <option value="{street_option_value}">{street_option_label}</option>
        </select>
        <select name="ladeort" id="ladeort">
            <option value="">Bitte wählen</option>
            <option value="00726-0035 ">Dragonerstr. 35, Hannover / Vahrenwald</option>
        </select>
    </body>
</html>
""".format(
    street_option_value=STREET_OPTION_VALUE,
    street_option_label=STREET_OPTION_LABEL,
)

RESPONSES_DIR = Path("tests/responses")


@pytest.fixture(name="session")
def fixture_session() -> AsyncMock:
    """Create an aiohttp session mock."""
    return AsyncMock()


@pytest.fixture(name="form_html_session")
def fixture_form_html_session(session: AsyncMock) -> AsyncMock:
    """Attach HTML form response to the mocked session."""
    response = AsyncMock()
    response.text.return_value = FORM_HTML
    session.post.return_value = response
    return session


@pytest.fixture(name="response_file_session")
def fixture_response_file_session(session: AsyncMock):
    """Return a helper that configures a response body from fixture files."""

    def _configure(filename: str) -> AsyncMock:
        response = AsyncMock()
        response.text.return_value = (RESPONSES_DIR / filename).read_text(
            encoding="utf-8"
        )
        session.post.return_value = response
        return session

    return _configure


@pytest.mark.asyncio
async def test_get_data_restabfall(response_file_session) -> None:
    """Test with 4 wastetypes and regular 'Restabfall'."""
    session = response_file_session("response_restabfall.html")
    api = AhaApi(session, "", "", 0, "", "")
    data = await api.get_data()

    assert len(data) == 4
    assert data["Restabfall"] == [
        "Mi, 11.10.2023",
        "Mi, 18.10.2023",
        "Mi, 25.10.2023",
    ]
    assert data["Bioabfall"] == [
        "Do, 12.10.2023",
        "Do, 19.10.2023",
        "Do, 26.10.2023",
    ]
    assert data["Papier"] == ["Fr, 13.10.2023", "Fr, 20.10.2023", "Fr, 27.10.2023"]
    assert data["Leichtverpackungen"] == [
        "Do, 12.10.2023",
        "Do, 19.10.2023",
        "Do, 26.10.2023",
    ]


@pytest.mark.asyncio
async def test_get_data_restabfall_660(response_file_session) -> None:
    """Test with 4 wastetypes and 'Restabfall 660/1.000 Liter'."""
    session = response_file_session("response_restabfall_660.html")
    api = AhaApi(session, "", "", 0, "", "")
    data = await api.get_data()

    assert len(data) == 4
    assert data["Restabfall 660/1.100 Liter"] == [
        "Mi, 11.10.2023",
        "Mi, 18.10.2023",
        "Mi, 25.10.2023",
    ]
    assert data["Bioabfall"] == [
        "Do, 12.10.2023",
        "Do, 19.10.2023",
        "Do, 26.10.2023",
    ]
    assert data["Papier"] == ["Fr, 13.10.2023", "Fr, 20.10.2023", "Fr, 27.10.2023"]
    assert data["Leichtverpackungen"] == [
        "Do, 12.10.2023",
        "Do, 19.10.2023",
        "Do, 26.10.2023",
    ]


@pytest.mark.asyncio
async def test_get_data_papier_leichtverpackungen(response_file_session) -> None:
    """Test with just 2 types of waste collected."""
    session = response_file_session("response_papier_leichtverpackungen.html")
    api = AhaApi(session, "", "", 0, "", "")
    data = await api.get_data()

    assert len(data) == 2
    assert data["Papier"] == ["Do, 12.10.2023", "Do, 19.10.2023", "Do, 26.10.2023"]
    assert data["Leichtverpackungen"] == [
        "Do, 12.10.2023",
        "Do, 19.10.2023",
        "Do, 26.10.2023",
    ]


@pytest.mark.asyncio
async def test_get_strassen_posts_selected_gemeinde(
    form_html_session: AsyncMock,
) -> None:
    """Test street scraping posts the municipality and parses streets."""
    api = AhaApi(form_html_session, "", "", 0, "", "")

    gemeinden = await api.get_gemeinden()
    initials = await api.get_street_initials("Hannover")
    data = await api.get_strassen("Hannover", "A")

    assert gemeinden == {"Hannover": "Hannover", "Laatzen": "Laatzen"}
    assert initials == {"A": "A", "D": "D"}
    assert data == {"Am Küchengarten / Linden-Mitte": STREET_OPTION_VALUE}
    assert form_html_session.post.await_count == 3
    assert form_html_session.post.await_args.kwargs["data"] == {
        "gemeinde": "Hannover",
        "von": "A",
    }


@pytest.mark.asyncio
async def test_get_ladeorte_posts_address_and_parses_options(
    form_html_session: AsyncMock,
) -> None:
    """Test pickup place scraping uses the full address payload."""
    api = AhaApi(form_html_session, "", "", 0, "", "")

    data = await api.get_ladeorte(
        "Hannover",
        "00726@Dragonerstr. / Vahrenwald@Vahrenwald",
        35,
        "",
    )

    assert data == {"Dragonerstr. 35, Hannover / Vahrenwald": "00726-0035 "}
    form_html_session.post.assert_awaited_once()
    assert form_html_session.post.await_args.kwargs["data"] == {
        "gemeinde": "Hannover",
        "strasse": "00726@Dragonerstr. / Vahrenwald@Vahrenwald",
        "hausnr": "35",
        "hausnraddon": "",
    }
