import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .coordinator import OrlenGasCoordinator
from .api import AuthError, ApiError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = OrlenGasCoordinator(
        hass,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )

    # Pierwsze logowanie — tutaj token zostaje zapamiętany w coordinator.api
    try:
        await hass.async_add_executor_job(coordinator.api.login)
    except AuthError as err:
        # Złe hasło — nie ma sensu retry, blokujemy entry
        raise ConfigEntryNotReady(f"Błąd logowania: {err}") from err
    except ApiError as err:
        raise ConfigEntryNotReady(f"Błąd API: {err}") from err

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
