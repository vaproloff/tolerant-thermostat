"""Constants for the Tolerant Thermostat."""

from homeassistant.const import Platform

DOMAIN = "tolerant_thermostat"

PLATFORMS = [Platform.CLIMATE]

DEFAULT_NAME = "Tolerant Thermostat"

CONF_AC_MODE = "ac_mode"
CONF_HEATER = "heater"
CONF_INVERTED = "inverted"
CONF_MIN_DUR = "min_cycle_duration"
CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"
CONF_TARGET_TEMP_HIGH = "target_temp_high"
CONF_TARGET_TEMP_LOW = "target_temp_low"
CONF_TEMP_STEP = "target_temp_step"
