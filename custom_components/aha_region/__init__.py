"""aha custom component """

from homeassistant import core

from .const import DOMAIN


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the aha component."""
    return True
