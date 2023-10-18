"""aha custom component."""

from homeassistant import core
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the aha component."""
    return True
