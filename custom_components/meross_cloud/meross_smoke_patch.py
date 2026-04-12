import logging
from typing import Optional

from meross_iot.controller.device import GenericSubDevice
from meross_iot.model.enums import OnlineStatus, Namespace

_LOGGER = logging.getLogger(__name__)


class Ms200WindowSensor(GenericSubDevice):
    """Best-effort support for Meross MS200 door/window sensors."""

    def _apply_online(self, online: dict) -> None:
        if not online:
            return
        try:
            self._online = OnlineStatus(online.get("status", -1))
        except Exception:
            self._online = OnlineStatus.UNKNOWN

    async def async_handle_push_notification(self, namespace: Namespace, data: dict) -> bool:
        handled_here = False

        if namespace == Namespace.HUB_SENSOR_ALL and data.get("id") == self.subdevice_id:
            self._apply_online(data.get("online", {}))
            handled_here = True
        elif namespace == Namespace.HUB_ONLINE and (
            data.get("id") == self.subdevice_id or "online" in data or "status" in data
        ):
            if "online" in data:
                self._apply_online(data.get("online", {}))
            elif "status" in data:
                self._apply_online({"status": data.get("status")})
            handled_here = True

        parent_handled = await super().async_handle_push_notification(namespace=namespace, data=data)
        return handled_here or parent_handled

    async def async_handle_subdevice_notification(self, namespace: Namespace, data: dict) -> bool:
        handled_here = False

        if namespace == Namespace.HUB_SENSOR_ALL:
            self._apply_online(data.get("online", {}))
            handled_here = True
        elif namespace == Namespace.HUB_ONLINE:
            if "online" in data:
                self._apply_online(data.get("online", {}))
            elif "status" in data:
                self._apply_online({"status": data.get("status")})
            handled_here = True

        return handled_here


class Gs559aSmokeAlarm(GenericSubDevice):
    """Best-effort support for Meross GS559A smoke alarm."""

    def __init__(self, hubdevice_uuid: str, subdevice_id: str, manager, **kwargs):
        super().__init__(hubdevice_uuid, subdevice_id, manager, **kwargs)
        self._last_active_time: Optional[int] = None
        self._smoke_status_raw: Optional[int] = None
        self._last_smoke_time: Optional[int] = None
        self._inter_conn: Optional[int] = None

    @property
    def smoke_status_raw(self) -> Optional[int]:
        return self._smoke_status_raw

    @property
    def last_smoke_time(self) -> Optional[int]:
        return self._last_smoke_time

    @property
    def inter_conn(self) -> Optional[int]:
        return self._inter_conn

    @property
    def is_alarm(self) -> Optional[bool]:
        # Based on observed logs, 170 appears to be idle/normal.
        if self._smoke_status_raw is None:
            return None
        return self._smoke_status_raw != 170

    def _apply_online(self, online: dict) -> None:
        if not online:
            return
        try:
            self._online = OnlineStatus(online.get("status", -1))
        except Exception:
            self._online = OnlineStatus.UNKNOWN
        self._last_active_time = online.get("lastActiveTime")

    def _apply_smoke(self, smoke: dict) -> None:
        if not smoke:
            return
        if "status" in smoke:
            self._smoke_status_raw = smoke.get("status")
        if "lmtime" in smoke:
            self._last_smoke_time = smoke.get("lmtime")
        if "interConn" in smoke:
            self._inter_conn = smoke.get("interConn")

    async def async_handle_push_notification(self, namespace: Namespace, data: dict) -> bool:
        handled_here = False

        if namespace == Namespace.HUB_SENSOR_ALL:
            if data.get("id") == self.subdevice_id:
                self._apply_online(data.get("online", {}))
                self._apply_smoke(data.get("smokeAlarm", {}))
                handled_here = True

        elif namespace == Namespace.HUB_ONLINE:
            if data.get("id") == self.subdevice_id or "online" in data:
                self._apply_online(data.get("online", {}))
                handled_here = True

        parent_handled = await super().async_handle_push_notification(namespace=namespace, data=data)
        return handled_here or parent_handled

    async def async_handle_subdevice_notification(self, namespace: Namespace, data: dict) -> bool:
        handled_here = False

        if namespace == Namespace.HUB_SENSOR_ALL:
            self._apply_online(data.get("online", {}))
            self._apply_smoke(data.get("smokeAlarm", {}))
            handled_here = True

        elif namespace == Namespace.HUB_ONLINE:
            self._apply_online(data.get("online", {}))
            handled_here = True

        return handled_here


def apply_smoke_alarm_patch():
    """
    Inject missing subdevice support into meross_iot at runtime.
    This avoids editing site-packages directly.
    """
    try:
        import meross_iot.device_factory as device_factory

        patched = False

        if hasattr(device_factory, "_KNOWN_DEV_TYPES_CLASSES"):
            device_factory._KNOWN_DEV_TYPES_CLASSES["gs559a"] = Gs559aSmokeAlarm
            device_factory._KNOWN_DEV_TYPES_CLASSES["ms200"] = Ms200WindowSensor
            patched = True

        if hasattr(device_factory, "_SUBDEVICE_MAPPING"):
            device_factory._SUBDEVICE_MAPPING["gs559a"] = Gs559aSmokeAlarm
            device_factory._SUBDEVICE_MAPPING["ms200"] = Ms200WindowSensor
            patched = True

        if patched:
            _LOGGER.warning("Applied Meross runtime patches for GS559A and MS200 subdevices")
        else:
            _LOGGER.warning("Meross runtime patch loaded, but no known device mapping table was found")

    except Exception as exc:
        _LOGGER.exception("Failed to apply Meross runtime patch: %s", exc)
