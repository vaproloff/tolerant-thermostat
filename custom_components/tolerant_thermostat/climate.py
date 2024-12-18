"""Adds support for Tolerant Thermostat units."""

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
import math
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import ConditionError
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA_COMMON = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP_HIGH): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP_LOW): vol.Coerce(float),
        vol.Optional(CONF_AC_MODE, default=False): cv.boolean,
        vol.Optional(CONF_INVERTED, default=False): cv.boolean,
        vol.Optional(CONF_MIN_DUR): cv.positive_time_period,
        vol.Optional(CONF_PRECISION): vol.All(
            vol.Coerce(float),
            vol.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]),
        ),
        vol.Optional(CONF_TEMP_STEP): vol.All(
            vol.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE])
        ),
    }
)

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_COMMON.schema)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await _async_setup_config(
        hass,
        PLATFORM_SCHEMA_COMMON(dict(config_entry.options)),
        config_entry.entry_id,
        async_add_entities,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the generic thermostat platform."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_config(
        hass, config, config.get(CONF_UNIQUE_ID), async_add_entities
    )


async def _async_setup_config(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    unique_id: str | None,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the generic thermostat platform."""

    name: str = config[CONF_NAME]
    heater_entity_id: str = config[CONF_HEATER]
    sensor_entity_id: str = config[CONF_SENSOR]
    min_temp: float | None = config.get(CONF_MIN_TEMP)
    max_temp: float | None = config.get(CONF_MAX_TEMP)
    target_temp_high: float | None = config.get(CONF_TARGET_TEMP_HIGH)
    target_temp_low: float | None = config.get(CONF_TARGET_TEMP_LOW)
    ac_mode: bool | None = config.get(CONF_AC_MODE)
    inverted: bool | None = config.get(CONF_INVERTED)
    min_cycle_duration: timedelta | None = config.get(CONF_MIN_DUR)
    precision: float | None = config.get(CONF_PRECISION)
    target_temperature_step: float | None = config.get(CONF_TEMP_STEP)
    unit = hass.config.units.temperature_unit

    async_add_entities(
        [
            TolerantThermostat(
                hass,
                name,
                heater_entity_id,
                sensor_entity_id,
                min_temp,
                max_temp,
                target_temp_high,
                target_temp_low,
                ac_mode,
                inverted,
                min_cycle_duration,
                precision,
                target_temperature_step,
                unit,
                unique_id,
            )
        ]
    )


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
        self._target_temp_step = target_temperature_step
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

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.sensor_entity_id], self._async_sensor_changed
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.heater_entity_id], self._async_switch_changed
            )
        )

        @callback
        def _async_startup(_: Event | None = None) -> None:
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_temp(sensor_state)
                self.async_write_ha_state()
            switch_state = self.hass.states.get(self.heater_entity_id)
            if switch_state and switch_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self.hass.async_create_task(
                    self._check_switch_initial_state(), eager_start=True
                )

        if self.hass.state is CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        if (old_state := await self.async_get_last_state()) is not None:
            if self._target_temp_low is None:
                old_target_low = old_state.attributes.get(ATTR_TARGET_TEMP_LOW)
                if old_target_low is not None:
                    self._target_temp_low = float(old_target_low)
                else:
                    _LOGGER.debug(
                        "%s: no target temperature low found in old state, falling back to default min_temp: %s",
                        self.entity_id,
                        self.min_temp,
                    )
                    self._target_temp_low = self.min_temp

            if self._target_temp_high is None:
                old_target_high = old_state.attributes.get(ATTR_TARGET_TEMP_HIGH)
                if old_target_high is not None:
                    self._target_temp_high = float(old_target_high)
                else:
                    _LOGGER.debug(
                        "%s: no target temperature high found in old state, falling back to default max_temp: %s",
                        self.entity_id,
                        self.max_temp,
                    )
                    self._target_temp_high = self.max_temp

            if old_state.state in self._attr_hvac_modes:
                self._hvac_mode = HVACMode(old_state.state)

        else:
            if self._target_temp_low is None:
                _LOGGER.warning(
                    "%s: no previously saved target low temperature, setting default: %s",
                    self.entity_id,
                    self.min_temp,
                )
                self._target_temp_low = self.min_temp

            if self._target_temp_high is None:
                _LOGGER.warning(
                    "%s: no previously saved target high temperature, setting default: %s",
                    self.entity_id,
                    self.max_temp,
                )
                self._target_temp_high = self.max_temp

        if not self._hvac_mode:
            _LOGGER.warning(
                "%s: no previously saved HVAC mode, setting default: %s",
                self.entity_id,
                HVACMode.OFF,
            )
            self._hvac_mode = HVACMode.OFF

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision

        return super().precision

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if self._target_temp_step is not None:
            return self._target_temp_step

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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.error("%s: unsupported hvac mode: %s", self.entity_id, hvac_mode)
            return

        if hvac_mode == self._hvac_mode:
            _LOGGER.info(
                "%s: no need to control. HVAC mode %s already set",
                self.entity_id,
                hvac_mode,
            )
            return

        self._hvac_mode = hvac_mode
        if self._hvac_mode == HVACMode.OFF and self._is_device_active:
            await self._async_heater_turn_off()
        else:
            await self._async_control(force=True)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if temp_low is None and temp_high is None:
            _LOGGER.warning("%s: undefined target temperatures", self.entity_id)
            return

        if temp_low is not None:
            self._target_temp_low = self._round_to_target_precision(temp_low)

        if temp_high is not None:
            self._target_temp_high = self._round_to_target_precision(temp_high)

        await self._async_control(force=True)
        self.async_write_ha_state()

    async def _async_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle temperature changes."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._async_update_temp(new_state)
        await self._async_control()
        self.async_write_ha_state()

    @callback
    def _async_switch_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle heater switch state changes."""
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]
        if new_state is None:
            return
        if old_state is None:
            self.hass.async_create_task(
                self._check_switch_initial_state(), eager_start=True
            )
        self.async_write_ha_state()

    async def _check_switch_initial_state(self) -> None:
        """Prevent the device from keep running if HVACMode.OFF."""
        if self._hvac_mode == HVACMode.OFF and self._is_device_active:
            _LOGGER.warning(
                "%s: hvac mode is OFF, but the target device is ON. Turning off device %s",
                self.entity_id,
                self.heater_entity_id,
            )
            await self._async_heater_turn_off()

    @callback
    def _async_update_temp(self, state: State) -> None:
        """Update thermostat with latest state from sensor."""
        try:
            cur_temp = float(state.state)
            if not math.isfinite(cur_temp):
                raise ValueError(  # noqa: TRY301
                    f"{self.entity_id}: sensor has illegal state: {state.state}"
                )
            self._cur_temp = cur_temp
        except ValueError as ex:
            _LOGGER.error("%s: unable to update from sensor: %s", self.entity_id, ex)

    async def _async_heater_turn_on(self) -> None:
        """Turn heater toggleable device on."""
        _LOGGER.debug(
            "%s: turning ON target device %s", self.entity_id, self.heater_entity_id
        )

        service = SERVICE_TURN_ON if not self._inverted else SERVICE_TURN_OFF
        service_data = {ATTR_ENTITY_ID: self.heater_entity_id}

        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN, service, service_data, context=self._context
        )

    async def _async_heater_turn_off(self) -> None:
        """Turn heater toggleable device off."""
        _LOGGER.debug(
            "%s: turning OFF target device %s", self.entity_id, self.heater_entity_id
        )

        service = SERVICE_TURN_OFF if not self._inverted else SERVICE_TURN_ON
        service_data = {ATTR_ENTITY_ID: self.heater_entity_id}

        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN, service, service_data, context=self._context
        )

    def _round_to_target_precision(self, value: float) -> float:
        step = self.target_temperature_step
        if step and value is not None:
            return round(value / step) * step

        return value

    async def _async_control(self, force: bool = False) -> None:
        """Check if we need to turn target device on or off."""
        if self._hvac_mode == HVACMode.OFF:
            return

        async with self._temp_lock:
            if not force and self.min_cycle_duration:
                if self._is_device_active:
                    current_state = STATE_ON
                else:
                    current_state = HVACMode.OFF

                try:
                    long_enough = condition.state(
                        self.hass,
                        self.heater_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                except ConditionError:
                    long_enough = False

                if not long_enough:
                    return

            assert None not in (
                self._cur_temp,
                self._target_temp_low,
                self._target_temp_high,
            )

            too_cold = self._cur_temp <= self._target_temp_low
            too_hot = self._cur_temp >= self._target_temp_high

            need_turn_on = (
                too_hot
                and self._hvac_mode == HVACMode.COOL
                or too_cold
                and self._hvac_mode == HVACMode.HEAT
            )

            need_turn_off = (
                too_cold
                and self._hvac_mode == HVACMode.COOL
                or too_hot
                and self._hvac_mode == HVACMode.HEAT
            )

            if self._is_device_active and need_turn_off:
                await self._async_heater_turn_off()
            elif not self._is_device_active and need_turn_on:
                await self._async_heater_turn_on()
