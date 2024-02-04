"""Tests for coordinator."""

from unittest.mock import AsyncMock

import pytest

from custom_components.aha_region.coordinator import AhaApi


@pytest.mark.asyncio
async def test_get_data_restabfall():
    """Test with 4 wastetypes and regular 'Restabfall'."""
    with open("tests/responses/response_restabfall.html") as file:
        response = AsyncMock()
        response.text.return_value = file.read()
        session = AsyncMock()
        session.post.return_value = response
        api = AhaApi(session, "", "", "", "", "")
        data = await api.get_data()

        assert len(data) == 4
        assert data["Restabfall"] == "Mi, 11.10.2023"
        assert data["Bioabfall"] == "Do, 12.10.2023"
        assert data["Papier"] == "Fr, 13.10.2023"
        assert data["Leichtverpackungen"] == "Do, 12.10.2023"


@pytest.mark.asyncio
async def test_get_data_restabfall_660():
    """Test with 4 wastetypes and 'Restabfall 660/1.000 Liter'."""
    with open("tests/responses/response_restabfall_660.html") as file:
        response = AsyncMock()
        response.text.return_value = file.read()
        session = AsyncMock()
        session.post.return_value = response
        api = AhaApi(session, "", "", "", "", "")
        data = await api.get_data()

        assert len(data) == 4
        assert data["Restabfall 660/1.100 Liter"] == "Mi, 11.10.2023"
        assert data["Bioabfall"] == "Do, 12.10.2023"
        assert data["Papier"] == "Fr, 13.10.2023"
        assert data["Leichtverpackungen"] == "Do, 12.10.2023"


@pytest.mark.asyncio
async def test_get_data_papier_leichtverpackungen():
    """Test with just 2 types of waste collected."""
    with open("tests/responses/response_papier_leichtverpackungen.html") as file:
        response = AsyncMock()
        response.text.return_value = file.read()
        session = AsyncMock()
        session.post.return_value = response
        api = AhaApi(session, "", "", "", "", "")
        data = await api.get_data()

        assert len(data) == 2
        assert data["Papier"] == "Do, 12.10.2023"
        assert data["Leichtverpackungen"] == "Do, 12.10.2023"
