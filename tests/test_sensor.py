"""Test sensor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.aha_region import sensor


@pytest.mark.asyncio
async def test_async_setup_platform_success():
    """Test async_setup_platform adds entities when coordinator returns data."""
    hass = MagicMock()
    async_add_entities = MagicMock()
    config = {
        sensor.CONF_GEMEINDE: "Gemeinde",
        sensor.CONF_HAUSNR: 1,
        sensor.CONF_STRASSE: "Straße",
        sensor.CONF_HAUSNRADDON: "A",
        sensor.CONF_ABHOLPLATZ: "Platz",
    }

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"Restmüll": "2024-06-01", "Papier": "2024-06-02"}
    mock_coordinator.async_refresh = AsyncMock()
    mock_coordinator.async_refresh.return_value = None

    with patch(
        "custom_components.aha_region.sensor.AhaUpdateCoordinator",
        return_value=mock_coordinator,
    ):
        await sensor.async_setup_platform(hass, config, async_add_entities)
        assert async_add_entities.called
        entities = async_add_entities.call_args[0][0]
        entity_names = [e._attr_name for e in entities]
        assert "Restmüll" in entity_names
        assert "Papier" in entity_names


@pytest.mark.asyncio
async def test_async_setup_platform_platform_not_ready():
    """Test async_setup_platform raises PlatformNotReady when no data is returned."""
    hass = MagicMock()
    async_add_entities = MagicMock()
    config = {
        sensor.CONF_GEMEINDE: "Gemeinde",
        sensor.CONF_HAUSNR: 1,
        sensor.CONF_STRASSE: "Straße",
    }

    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_coordinator.async_refresh = AsyncMock()
    mock_coordinator.async_refresh.return_value = None

    with patch(
        "custom_components.aha_region.sensor.AhaUpdateCoordinator",
        return_value=mock_coordinator,
    ), patch(
        "custom_components.aha_region.sensor.async_get_clientsession",
        return_value=MagicMock(),
    ):
        with pytest.raises(sensor.PlatformNotReady):
            await sensor.async_setup_platform(hass, config, async_add_entities)


def test_aha_waste_sensor_properties():
    """Test AhaWasteSensor properties are set correctly."""
    coordinator = MagicMock()
    coordinator.data = {"Restmüll": "2024-06-01"}
    sensor_entity = sensor.AhaWasteSensor(coordinator, "Restmüll", "baseid")
    assert sensor_entity._attr_name == "Restmüll"
    assert sensor_entity._attr_unique_id == "baseid_Restmüll"
    assert sensor_entity.available is True
    assert sensor_entity.native_value == "2024-06-01"


@pytest.mark.asyncio
async def test_aha_waste_sensor_update():
    """Test async_update calls coordinator.async_request_refresh."""
    coordinator = MagicMock()
    coordinator.data = {"Restmüll": "2024-06-01"}
    coordinator.async_request_refresh = AsyncMock()
    sensor_entity = sensor.AhaWasteSensor(coordinator, "Restmüll", "baseid")
    await sensor_entity.async_update()
    assert coordinator.async_request_refresh.called


def test_aha_waste_sensor_handle_coordinator_update():
    """Test _handle_coordinator_update updates native_value and writes state."""
    coordinator = MagicMock()
    coordinator.data = {"Restmüll": "2024-06-01"}
    sensor_entity = sensor.AhaWasteSensor(coordinator, "Restmüll", "baseid")
    sensor_entity.async_write_ha_state = MagicMock()
    coordinator.data["Restmüll"] = "2024-07-01"
    sensor_entity._handle_coordinator_update()
    assert sensor_entity.native_value == "2024-07-01"
    assert sensor_entity.async_write_ha_state.called
