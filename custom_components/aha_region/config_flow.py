"""Config flow for aha_region."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CONF_ABHOLPLATZ,
    CONF_GEMEINDE,
    CONF_HAUSNR,
    CONF_HAUSNRADDON,
    CONF_STRASSE,
    DOMAIN,
)
from .coordinator import AhaApi

CONF_STREET_INITIAL = "street_initial"


class AhaRegionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for aha_region."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, str | int] = {}
        self._gemeinden: dict[str, str] = {}
        self._street_initials: dict[str, str] = {}
        self._strassen: dict[str, str] = {}
        self._ladeorte: dict[str, str] = {}
        self._selected_strassen_label = ""
        self._selected_street_initial = ""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Select a municipality."""
        errors: dict[str, str] = {}

        if user_input is not None:
            gemeinde_label = user_input[CONF_GEMEINDE]
            self._data[CONF_GEMEINDE] = self._gemeinden[gemeinde_label]
            return await self.async_step_street_initial()

        try:
            self._gemeinden = await self._get_api().get_gemeinden()
        except (ClientError, TimeoutError, asyncio.TimeoutError):
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GEMEINDE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(self._gemeinden.keys())
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_street_initial(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Select the first letter of the street name."""
        errors: dict[str, str] = {}

        try:
            if not self._street_initials:
                self._street_initials = await self._get_api().get_street_initials(
                    str(self._data[CONF_GEMEINDE])
                )
        except (ClientError, TimeoutError, asyncio.TimeoutError):
            errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            initial_label = user_input[CONF_STREET_INITIAL]
            self._selected_street_initial = self._street_initials[initial_label]
            self._strassen = {}
            return await self.async_step_address()

        return self.async_show_form(
            step_id="street_initial",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREET_INITIAL): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(self._street_initials.keys())
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_address(
        self, user_input: dict[str, str | int] | None = None
    ) -> FlowResult:
        """Select the street and house number."""
        errors: dict[str, str] = {}
        default_strasse = user_input.get(CONF_STRASSE) if user_input else None
        default_hausnr = user_input.get(CONF_HAUSNR) if user_input else None
        default_hausnraddon = user_input.get(CONF_HAUSNRADDON) if user_input else ""

        try:
            if not self._strassen:
                self._strassen = await self._get_api().get_strassen(
                    str(self._data[CONF_GEMEINDE]),
                    self._selected_street_initial,
                )
        except (ClientError, TimeoutError, asyncio.TimeoutError):
            errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            strassen_label = str(user_input[CONF_STRASSE])
            hausnr = int(user_input[CONF_HAUSNR])
            hausnraddon = str(user_input.get(CONF_HAUSNRADDON, ""))
            self._selected_strassen_label = strassen_label
            self._data[CONF_STRASSE] = self._strassen[strassen_label]
            self._data[CONF_HAUSNR] = hausnr
            self._data[CONF_HAUSNRADDON] = hausnraddon

            try:
                self._ladeorte = await self._get_api().get_ladeorte(
                    str(self._data[CONF_GEMEINDE]),
                    str(self._data[CONF_STRASSE]),
                    hausnr,
                    hausnraddon,
                )
            except (ClientError, TimeoutError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"

            if not errors and self._ladeorte:
                if len(self._ladeorte) == 1:
                    self._data[CONF_ABHOLPLATZ] = next(iter(self._ladeorte.values()))
                    return await self._async_validate_and_create_entry()
                return await self.async_step_ladeort()

            if not errors:
                self._data[CONF_ABHOLPLATZ] = ""
                return await self._async_validate_and_create_entry()

        return self._show_address_form(
            errors,
            default_strasse,
            default_hausnr,
            default_hausnraddon,
        )

    async def async_step_ladeort(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Select the pickup place when the address requires one."""
        if user_input is not None:
            ladeort_label = user_input[CONF_ABHOLPLATZ]
            self._data[CONF_ABHOLPLATZ] = self._ladeorte[ladeort_label]
            return await self._async_validate_and_create_entry()

        return self.async_show_form(
            step_id="ladeort",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ABHOLPLATZ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=sorted(self._ladeorte.keys()))
                    )
                }
            ),
            errors={},
        )

    async def _async_validate_and_create_entry(self) -> FlowResult:
        """Validate the selected address against the calendar page."""
        try:
            data = await self._get_api(self._data).get_data()
        except (ClientError, TimeoutError, asyncio.TimeoutError):
            return self._show_address_form(
                {"base": "cannot_connect"},
                self._selected_strassen_label,
                int(self._data[CONF_HAUSNR]),
                str(self._data[CONF_HAUSNRADDON]),
            )

        if not data:
            return self._show_address_form(
                {"base": "invalid_address"},
                self._selected_strassen_label,
                int(self._data[CONF_HAUSNR]),
                str(self._data[CONF_HAUSNRADDON]),
            )

        entry_unique_id = self._build_unique_id(self._data)
        await self.async_set_unique_id(entry_unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._build_entry_title(),
            data=self._data,
        )

    def _show_address_form(
        self,
        errors: dict[str, str],
        default_strasse: object,
        default_hausnr: object,
        default_hausnraddon: object,
    ) -> FlowResult:
        """Show the address step with the latest defaults."""
        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STRASSE, default=default_strasse
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=sorted(self._strassen.keys()))
                    ),
                    vol.Required(CONF_HAUSNR, default=default_hausnr): vol.Coerce(int),
                    vol.Optional(
                        CONF_HAUSNRADDON, default=default_hausnraddon
                    ): str,
                }
            ),
            errors=errors,
        )

    @callback
    def _get_api(self, data: Mapping[str, str | int] | None = None) -> AhaApi:
        """Create an API helper from the current flow data."""
        api_data = data or self._data
        return AhaApi(
            async_get_clientsession(self.hass),
            str(api_data.get(CONF_GEMEINDE, "")),
            str(api_data.get(CONF_STRASSE, "")),
            int(api_data.get(CONF_HAUSNR, 0)),
            str(api_data.get(CONF_HAUSNRADDON, "")),
            str(api_data.get(CONF_ABHOLPLATZ, "")),
        )

    @staticmethod
    def _build_unique_id(data: Mapping[str, str | int]) -> str:
        """Build a unique id for an address configuration."""
        return slugify(
            "".join(
                [
                    str(data.get(CONF_GEMEINDE, "")),
                    str(data.get(CONF_STRASSE, "")),
                    str(data.get(CONF_HAUSNR, "")),
                    str(data.get(CONF_HAUSNRADDON, "")),
                    str(data.get(CONF_ABHOLPLATZ, "")),
                ]
            )
        )

    def _build_entry_title(self) -> str:
        """Build a readable title for the config entry."""
        hausnraddon = str(self._data[CONF_HAUSNRADDON]).strip()
        title = (
            f"{self._selected_strassen_label} {self._data[CONF_HAUSNR]}"
            f"{hausnraddon}, {self._data[CONF_GEMEINDE]}"
        )
        return title.strip()

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Return True when two in-progress flows target the same address."""
        del other_flow
        return False
