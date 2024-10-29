"""Adds support for Tolerant Thermostat units."""

import asyncio
from datetime import timedelta

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity


class TolerantThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Tolerant Thermostat device."""

    _attr_should_poll = False
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        heater_entity_id: str,
        sensor_entity_id: str,
        min_temp: float | None,
        max_temp: float | None,
        target_temp_high: float | None,
        target_temp_low: float | None,
        ac_mode: bool | None,
        inverted: bool | None,
        min_cycle_duration: timedelta | None,
        presets: dict[str, float],
        precision: float | None,
        target_temperature_step: float | None,
        unit: UnitOfTemperature,
        unique_id: str | None,
    ) -> None:
        """Initialize the thermostat."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self._ac_mode = ac_mode
        self._inverted = inverted
        self.min_cycle_duration = min_cycle_duration
        self._hvac_mode = HVACMode.OFF
        self._temp_precision = precision
        self._temp_target_temperature_step = target_temperature_step
        self._cur_temp: float | None = None
        self._temp_lock = asyncio.Lock()
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp_high = target_temp_high
        self._target_temp_low = target_temp_low
        self._attr_temperature_unit = unit

        if self._inverted:
            self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
        else:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        self._attr_preset_mode = PRESET_NONE
        if len(presets):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_NONE, *presets.keys()]
        else:
            self._attr_preset_modes = [PRESET_NONE]
        self._presets = presets

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision

        return super().precision

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if self._temp_target_temperature_step is not None:
            return self._temp_target_temperature_step

        return self.precision

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        return super().max_temp

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        if not self._is_device_active:
            return HVACAction.IDLE

        return HVACAction.COOLING if self._ac_mode else HVACAction.HEATING

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound temperature."""
        return self._target_temp_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound temperature."""
        return self._target_temp_high

    @property
    def _is_device_active(self) -> bool | None:
        """If the toggleable device is currently active."""
        if not self.hass.states.get(self.heater_entity_id):
            return None

        return self.hass.states.is_state(
            self.heater_entity_id, STATE_ON if not self._inverted else STATE_OFF
        )
