import logging
from datetime import timedelta
from typing import Optional, Dict

from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.garage import GarageOpenerMixin
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.controller.mixins.dnd import SystemDndMixin
from meross_iot.controller.mixins.toggle import ToggleXMixin, ToggleMixin
from meross_iot.manager import MerossManager
from meross_iot.model.http.device import HttpDeviceInfo
from meross_iot.model.enums import DNDMode

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, DEVICE_LIST_COORDINATOR, HA_SWITCH, HA_STATE_POLL_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=HA_STATE_POLL_INTERVAL_SECONDS)


class MerossSwitchDevice(ToggleXMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class MerossDndDevice(SystemDndMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class SwitchEntityWrapper(MerossDevice, SwitchEntity):
    """Wrapper class to adapt the Meross switches into the Home Assistant platform"""
    _device: MerossSwitchDevice
    _attr_should_poll = True

    _attr_is_on: Optional[bool] = None

    def __init__(
        self,
        channel: int,
        device: MerossSwitchDevice,
        device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]
    ):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_SWITCH
        )
    async def async_update(self):
        if self.online:
            if not await super().async_update():
                return

            try:
                self._attr_is_on = self._device.is_on(channel=self._channel_id)
            except Exception as exc:
                _LOGGER.debug(
                    "Failed to read switch state for %s channel %s: %s",
                    self.name,
                    self._channel_id,
                    exc
                )

    @property
    def is_on(self) -> Optional[bool]:
        return self._attr_is_on

    async def async_turn_off(self, **kwargs) -> None:
        dev = self._device
        await dev.async_turn_off(channel=self._channel_id, skip_rate_limits=True)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        dev = self._device
        await dev.async_turn_on(channel=self._channel_id, skip_rate_limits=True)
        self._attr_is_on = True
        self.async_write_ha_state()


class DndEntityWrapper(MerossDevice, SwitchEntity):
    """Wrapper class to adapt the Meross DND switch into the Home Assistant platform"""
    _device: MerossDndDevice

    _attr_should_poll = True
    _dnd_mode: Optional[DNDMode] = None

    def __init__(
        self,
        device: MerossDndDevice,
        device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]
    ):
        super().__init__(
            device=device,
            channel=-1,
            device_list_coordinator=device_list_coordinator,
            platform=HA_SWITCH,
            override_channel_name="Do Not Disturb"
        )

    async def async_update(self):
        if self.online:
            if not await super().async_update():
                return
            try:
                self._dnd_mode = await self._device.async_get_dnd_mode()
            except Exception as exc:
                _LOGGER.debug(
                    "Failed to read DND mode for %s: %s",
                    self.name,
                    exc
                )

    @property
    def is_on(self) -> bool | None:
        if self._dnd_mode is None:
            return None
        return self._dnd_mode == DNDMode.DND_DISABLED

    async def async_turn_off(self, **kwargs) -> None:
        dev = self._device
        await dev.set_dnd_mode(mode=DNDMode.DND_ENABLED, skip_rate_limits=True)
        self._dnd_mode = DNDMode.DND_ENABLED
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        dev = self._device
        await dev.set_dnd_mode(mode=DNDMode.DND_DISABLED, skip_rate_limits=True)
        self._dnd_mode = DNDMode.DND_DISABLED
        self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and add new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        devs = filter(lambda d: isinstance(d, ToggleXMixin) or isinstance(d, ToggleMixin), devices)
        devs = filter(lambda d: not (isinstance(d, GarageOpenerMixin) or isinstance(d, LightMixin)), devs)

        for d in devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = SwitchEntityWrapper(
                    device=d,
                    channel=channel_index,
                    device_list_coordinator=coordinator
                )
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        dnd_switches = filter(lambda d: isinstance(d, SystemDndMixin), devices)
        for d in dnd_switches:
            w = DndEntityWrapper(device=d, device_list_coordinator=coordinator)
            if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                new_entities.append(w)

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    entity_adder_callback()


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
