"""Config flow for Tolerant Thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import fan, input_boolean, switch
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_NAME, DEGREE
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AC_MODE,
    CONF_HEATER,
    CONF_INVERTED,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_SENSOR,
    CONF_TARGET_TEMP_HIGH,
    CONF_TARGET_TEMP_LOW,
    CONF_TEMP_STEP,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    vol.Required(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
        )
    ),
    vol.Required(CONF_HEATER): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=[fan.DOMAIN, switch.DOMAIN, input_boolean.DOMAIN]
        )
    ),
    vol.Required(CONF_AC_MODE): selector.BooleanSelector(
        selector.BooleanSelectorConfig(),
    ),
    vol.Required(CONF_INVERTED): selector.BooleanSelector(
        selector.BooleanSelectorConfig(),
    ),
    vol.Optional(CONF_MIN_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=1
        )
    ),
    vol.Optional(CONF_MAX_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=1
        )
    ),
    vol.Optional(CONF_TARGET_TEMP_HIGH): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.5
        )
    ),
    vol.Optional(CONF_TARGET_TEMP_LOW): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.5
        )
    ),
    vol.Optional(CONF_PRECISION): selector.NumberSelector(
        selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=0.1)
    ),
    vol.Optional(CONF_TEMP_STEP): selector.NumberSelector(
        selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=0.1)
    ),
    vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(
            enable_day=False, enable_millisecond=False, allow_negative=False
        )
    ),
}

CONFIG_SCHEMA = {
    vol.Required(CONF_NAME): selector.TextSelector(),
    **OPTIONS_SCHEMA,
}


CONFIG_FLOW = {"user": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA))}

OPTIONS_FLOW = {"init": SchemaFlowFormStep(vol.Schema(OPTIONS_SCHEMA))}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    MINOR_VERSION = 3

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
