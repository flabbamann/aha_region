"""constants for aha custom component."""
import logging
from typing import Final

CONF_GEMEINDE: Final = "gemeinde"
CONF_HAUSNR: Final = "hausnr"
CONF_HAUSNRADDON: Final = "hausnraddon"
CONF_STRASSE: Final = "strasse"
CONF_ABHOLPLATZ: Final = "abholplatz"

DOMAIN: Final = "aha_region"

ABFALLARTEN: Final = ["Restabfall", "Bioabfall", "Papier", "Leichtverpackungen"]

LOGGER = logging.getLogger(__package__)

URL: Final = "https://www.aha-region.de/abholtermine/abfuhrkalender"
