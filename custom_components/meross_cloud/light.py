#Baiban update v1
#Fixed lighting blubs with white issues

import logging
from datetime import timedelta
from typing import Optional, Dict, Any

from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.controller.mixins.diffuser_light import DiffuserLightMixin
from meross_iot.manager import MerossManager
from meross_iot.model.http.device import HttpDeviceInfo
from meross_iot.model.enums import DiffuserLightMode
import homeassistant.util.color as color_util
from homeassistant.components.light import LightEntity
from homeassistant.components.light import (
    ColorMode,
    ATTR_HS_COLOR,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_LIGHT, DEVICE_LIST_COORDINATOR, HA_STATE_POLL_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=HA_STATE_POLL_INTERVAL_SECONDS)


def _kelvin_to_meross_temp(kelvin: int, min_k: int, max_k: int) -> int:
    norm_value = (kelvin - min_k) / (max_k - min_k)
    norm_value = max(0, min(1, norm_value))
    temperature = round(1 + (norm_value * 99))
    return max(1, min(100, temperature))


def _meross_temp_to_kelvin(temperature: int, min_k: int, max_k: int) -> int:
    temperature = max(1, min(100, temperature))
    norm_value = (temperature - 1) / 99
    kelvin = min_k + (norm_value * (max_k - min_k))
    return round(kelvin)


class MerossOilDiffuserLightDevice(DiffuserLightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class MerossLightDevice(LightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class DiffuserLightEntityWrapper(MerossDevice, LightEntity):
    """Wrapper class to adapt the Meross OilDiffuserLight"""
    _device: MerossOilDiffuserLightDevice
    _attr_should_poll = True
    _attr_supported_color_modes = {ColorMode.WHITE, ColorMode.RGB, ColorMode.COLOR_TEMP}

    def __init__(
        self,
        channel: int,
        device: MerossOilDiffuserLightDevice,
        device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
    ):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_LIGHT,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_turn_off(channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self.is_on:
            await self._device.async_turn_on(channel=self._channel_id, skip_rate_limits=True)

        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r", rgb, h, s)
            await self._device.async_set_light_mode(
                channel=self._channel_id,
                mode=DiffuserLightMode.FIXED_RGB,
                rgb=rgb,
                onoff=True,
                skip_rate_limits=True,
            )

        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            min_k = self.min_color_temp_kelvin
            max_k = self.max_color_temp_kelvin

            if min_k is not None and max_k is not None and max_k != min_k:
                temperature = _kelvin_to_meross_temp(kelvin, min_k, max_k)

                _LOGGER.debug("temperature change: kelvin=%r meross=%r", kelvin, temperature)
                await self._device.async_set_light_mode(
                    channel=self._channel_id,
                    mode=DiffuserLightMode.FIXED_LUMINANCE,
                    onoff=True,
                    rgb=65293,
                    brightness=temperature,
                    skip_rate_limits=True,
                )

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            brightness = max(1, min(100, round(brightness)))
            _LOGGER.debug("brightness change: %r", brightness)
            await self._device.async_set_light_mode(
                channel=self._channel_id,
                luminance=brightness,
                skip_rate_limits=True,
            )

    @property
    def is_on(self) -> Optional[bool]:
        return self._device.get_light_is_on(channel=self._channel_id)

    @property
    def hs_color(self):
        rgb = self._device.get_light_rgb_color(channel=self._channel_id)
        if rgb is not None and isinstance(rgb, tuple) and len(rgb) == 3:
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def brightness(self):
        luminance = self._device.get_light_brightness()
        if luminance is not None:
            return float(luminance) / 100 * 255
        return None

    @property
    def min_color_temp_kelvin(self) -> int | None:
        return 2000

    @property
    def max_color_temp_kelvin(self) -> int | None:
        return 6535

    @property
    def color_temp_kelvin(self) -> int | None:
        return None


class LightEntityWrapper(MerossDevice, LightEntity):
    """Wrapper class to adapt the Meross bulbs into the Homeassistant platform"""
    _device: MerossLightDevice
    _attr_should_poll = True

    def __init__(
        self,
        channel: int,
        device: MerossLightDevice,
        device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
    ):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_LIGHT,
        )
        self._last_color_mode: ColorMode | None = None

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_turn_off(channel=self._channel_id, skip_rate_limits=True)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        payload: dict[str, Any] = {
            "channel": self._channel_id,
            "onoff": True,
            "skip_rate_limits": True,
        }

        if ATTR_RGB_COLOR in kwargs:
            self._last_color_mode = ColorMode.RGB
            payload["rgb"] = kwargs[ATTR_RGB_COLOR]

        elif ATTR_HS_COLOR in kwargs:
            self._last_color_mode = ColorMode.RGB
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r", rgb, h, s)
            payload["rgb"] = rgb

        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._last_color_mode = ColorMode.COLOR_TEMP
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            min_k = self.min_color_temp_kelvin
            max_k = self.max_color_temp_kelvin

            if min_k is not None and max_k is not None and max_k != min_k:
                temperature = _kelvin_to_meross_temp(kelvin, min_k, max_k)
                _LOGGER.debug("temperature change: kelvin=%r meross=%r", kelvin, temperature)
                payload["temperature"] = temperature

        if ATTR_BRIGHTNESS in kwargs:
            if self._last_color_mode is None and self._device.get_supports_luminance(self._channel_id):
                self._last_color_mode = ColorMode.WHITE
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            brightness = max(1, min(100, round(brightness)))
            _LOGGER.debug("brightness change: %r", brightness)
            payload["luminance"] = brightness

        if len(payload) > 3:
            await self._device.async_set_light_color(**payload)
        elif not self.is_on:
            await self._device.async_turn_on(channel=self._channel_id, skip_rate_limits=True)

        self.async_write_ha_state()

    async def async_update(self):
        if not await super().async_update():
            return
        self._update_last_color_mode()

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        res = set()
        if self._device.get_supports_luminance(channel=self._channel_id):
            res.add(ColorMode.WHITE)
        if self._device.get_supports_rgb(channel=self._channel_id):
            res.add(ColorMode.RGB)
        if self._device.get_supports_temperature(channel=self._channel_id):
            res.add(ColorMode.COLOR_TEMP)
        if len(res) < 1:
            res.add(ColorMode.ONOFF)
        return res

    @property
    def is_on(self) -> Optional[bool]:
        return self._device.get_light_is_on(channel=self._channel_id)

    @property
    def brightness(self):
        if not self._device.get_supports_luminance(self._channel_id):
            return None

        luminance = self._device.get_luminance(channel=self._channel_id)
        if luminance is not None:
            return float(luminance) / 100 * 255

        return None

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        self._update_last_color_mode()
        if self._last_color_mode is not None:
            return self._last_color_mode

        if self._device.get_supports_luminance(channel=self._channel_id):
            return ColorMode.WHITE
        return ColorMode.ONOFF

    @property
    def hs_color(self):
        rgb = self._device.get_rgb_color(channel=self._channel_id)
        if rgb is not None and isinstance(rgb, tuple) and len(rgb) == 3:
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def min_color_temp_kelvin(self) -> int | None:
        if self._device.get_supports_temperature(channel=self._channel_id):
            return 2000
        return None

    @property
    def max_color_temp_kelvin(self) -> int | None:
        if self._device.get_supports_temperature(channel=self._channel_id):
            return 6535
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        if self._device.get_supports_temperature(channel=self._channel_id):
            value = self._device.get_color_temperature()
            if value is None:
                return None

            min_k = self.min_color_temp_kelvin
            max_k = self.max_color_temp_kelvin
            if min_k is None or max_k is None or max_k == min_k:
                return None

            return _meross_temp_to_kelvin(value, min_k, max_k)

        return None

    def _update_last_color_mode(self) -> None:
        if self._device.get_supports_rgb(channel=self._channel_id):
            hs = self.hs_color
            if hs is not None and hs[1] > 5:
                self._last_color_mode = ColorMode.RGB
                return

        if self._device.get_supports_temperature(channel=self._channel_id):
            color_temp = self.color_temp_kelvin
            if color_temp is not None:
                self._last_color_mode = ColorMode.COLOR_TEMP
                return

        if self._device.get_supports_luminance(channel=self._channel_id):
            self._last_color_mode = ColorMode.WHITE
            return

        self._last_color_mode = ColorMode.ONOFF


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        light_devs = filter(lambda d: isinstance(d, LightMixin), devices)
        for d in light_devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = LightEntityWrapper(
                    device=d,
                    channel=channel_index,
                    device_list_coordinator=coordinator,
                )
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        diffuser_devs = filter(lambda d: isinstance(d, DiffuserLightMixin), devices)
        for d in diffuser_devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = DiffuserLightEntityWrapper(
                    device=d,
                    channel=channel_index,
                    device_list_coordinator=coordinator,
                )
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    entity_adder_callback()


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
