"""Tests for config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.aha_region import async_setup
from custom_components.aha_region.config_flow import AhaRegionConfigFlow
from custom_components.aha_region.const import (
    CONF_ABHOLPLATZ,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
)


@pytest.fixture(name="flow")
def fixture_flow() -> AhaRegionConfigFlow:
    """Create a config flow instance with a mocked hass object."""
    config_flow = AhaRegionConfigFlow()
    config_flow.hass = MagicMock()
    return config_flow


@pytest.fixture(name="mock_api")
def fixture_mock_api() -> MagicMock:
    """Create a reusable API mock for flow tests."""
    api = MagicMock()
    api.get_gemeinden = AsyncMock(return_value={"Hannover": "Hannover"})
    api.get_street_initials = AsyncMock(return_value={"A": "A", "D": "D"})
    api.get_strassen = AsyncMock(
        return_value={
            "Am Küchengarten / Linden-Mitte": (
                "00152@Am Küchengarten / Linden-Mitte@Linden-Mitte"
            )
        }
    )
    api.get_ladeorte = AsyncMock(return_value={})
    api.get_data = AsyncMock(return_value={"Restabfall": ["Mi, 11.10.2023"]})
    return api


@pytest.mark.asyncio
async def test_async_step_user_shows_municipality_form(
    flow: AhaRegionConfigFlow, mock_api: MagicMock
) -> None:
    """Test that the first step loads municipality options."""
    with patch.object(flow, "_get_api", return_value=mock_api):
        result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_async_step_address_creates_entry_without_ladeort(
    flow: AhaRegionConfigFlow, mock_api: MagicMock
) -> None:
    """Test that a valid address creates a config entry directly."""
    with (
        patch.object(flow, "_get_api", return_value=mock_api),
        patch.object(flow, "async_set_unique_id", AsyncMock()),
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        await flow.async_step_user()
        result = await flow.async_step_user({CONF_GEMEINDE: "Hannover"})
        assert result["type"] == "form"
        assert result["step_id"] == "street_initial"
        await flow.async_step_street_initial({"street_initial": "A"})
        result = await flow.async_step_address(
            {
                CONF_STRASSE: "Am Küchengarten / Linden-Mitte",
                CONF_HAUSNR: 11,
                CONF_HAUSNRADDON: "a",
            }
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Am Küchengarten / Linden-Mitte 11a, Hannover"
    assert result["data"] == {
        CONF_GEMEINDE: "Hannover",
        CONF_STRASSE: "00152@Am Küchengarten / Linden-Mitte@Linden-Mitte",
        CONF_HAUSNR: 11,
        CONF_HAUSNRADDON: "a",
        CONF_ABHOLPLATZ: "",
    }


@pytest.mark.asyncio
async def test_async_step_address_routes_to_ladeort_step(
    flow: AhaRegionConfigFlow, mock_api: MagicMock
) -> None:
    """Test that the flow shows the pickup place step when required."""
    mock_api.get_strassen = AsyncMock(
        return_value={
            "Dragonerstr. / Vahrenwald": ("00726@Dragonerstr. / Vahrenwald@Vahrenwald")
        }
    )
    mock_api.get_ladeorte = AsyncMock(
        return_value={
            "Dragonerstr. 35, Hannover / Vahrenwald": "00726-0035 ",
            "Dragonerstr. 35, Hannover / Vahrenwald (Nord)": "00726-0035N ",
        }
    )

    with patch.object(flow, "_get_api", return_value=mock_api):
        await flow.async_step_user()
        result = await flow.async_step_user({CONF_GEMEINDE: "Hannover"})
        assert result["type"] == "form"
        assert result["step_id"] == "street_initial"
        await flow.async_step_street_initial({"street_initial": "D"})
        result = await flow.async_step_address(
            {
                CONF_STRASSE: "Dragonerstr. / Vahrenwald",
                CONF_HAUSNR: 35,
                CONF_HAUSNRADDON: "",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "ladeort"


@pytest.mark.asyncio
async def test_async_step_import_creates_entry(
    flow: AhaRegionConfigFlow, mock_api: MagicMock
) -> None:
    """Test that YAML import creates an entry."""
    user_input: dict[str, str | int] = {
        CONF_GEMEINDE: "Hannover",
        CONF_STRASSE: "00152@Am Küchengarten / Linden-Mitte@Linden-Mitte",
        CONF_HAUSNR: 11,
        CONF_HAUSNRADDON: "a",
        CONF_ABHOLPLATZ: "",
    }

    with patch.object(flow, "_get_api", return_value=mock_api), patch.object(
        flow, "async_set_unique_id", AsyncMock()
    ), patch.object(flow, "_abort_if_unique_id_configured"):
        result = await flow.async_step_import(user_input)

    assert result["type"] == "create_entry"
    assert result["data"] == user_input


@pytest.mark.asyncio
async def test_async_setup_imports_yaml_configuration() -> None:
    """Test YAML config is scheduled for config entry import without blocking startup."""
    config = {
        "sensor": [
            {
                "platform": "aha_region",
                CONF_GEMEINDE: "Hannover",
                CONF_STRASSE: "00152@Am Küchengarten / Linden-Mitte@Linden-Mitte",
                CONF_HAUSNR: 11,
                CONF_HAUSNRADDON: "a",
                CONF_ABHOLPLATZ: "",
            }
        ]
    }
    hass = MagicMock()
    hass.async_create_task = MagicMock(
        side_effect=lambda coro: asyncio.create_task(coro)
    )
    hass.config_entries.flow.async_init = AsyncMock(
        return_value={"type": "create_entry"}
    )

    assert await async_setup(hass, config) is True
    await asyncio.sleep(0)

    hass.async_create_task.assert_called_once()
    assert (
        hass.config_entries.flow.async_init.call_args.kwargs["context"]["source"]
        == "import"
    )
