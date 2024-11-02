"""The Tolerant Thermostat component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)

from .const import CONF_HEATER, CONF_PRECISION, CONF_TEMP_STEP, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        entry.options[CONF_HEATER],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version == 1:
        if entry.minor_version < 3:
            new_options = {**entry.options}
            if precision := new_options.get(CONF_PRECISION):
                new_options[CONF_PRECISION] = float(precision)
            if temp_step := new_options.get(CONF_TEMP_STEP):
                new_options[CONF_TEMP_STEP] = float(temp_step)

            hass.config_entries.async_update_entry(
                entry, options=new_options, minor_version=3
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
