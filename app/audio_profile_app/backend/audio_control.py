from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger("audio_profile")
try:
    from core.issue_log import log_issue
except Exception:
    def log_issue(*_args, **_kwargs):
        return

PYCAW_AVAILABLE = False
try:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
    try:
        from comtypes import CoInitializeEx, COINIT_MULTITHREADED
    except Exception:
        CoInitializeEx = None
        COINIT_MULTITHREADED = None
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    PYCAW_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    logger.warning("PyCaw unavailable: %s", exc)
    AudioUtilities = None
    IAudioEndpointVolume = None
    CLSCTX_ALL = None
    CoInitialize = None
    CoUninitialize = None
    CoInitializeEx = None
    COINIT_MULTITHREADED = None
    POINTER = None
    cast = None


def _ensure() -> None:
    if not PYCAW_AVAILABLE:
        raise RuntimeError("PyCaw not available")


@contextmanager
def _com_session():
    if not PYCAW_AVAILABLE or CoInitialize is None or CoUninitialize is None:
        yield
        return
    initialized = False
    try:
        if CoInitializeEx is not None and COINIT_MULTITHREADED is not None:
            try:
                CoInitializeEx(COINIT_MULTITHREADED)
                initialized = True
            except Exception as exc:
                logger.warning("COM init failed: %s", exc)
                log_issue("PHX-AUD-020", "com_init_failed", str(exc), source="audio_control")
                try:
                    CoInitialize()
                    initialized = True
                except Exception as exc2:
                    logger.warning("COM init fallback failed: %s", exc2)
                    log_issue("PHX-AUD-020", "com_init_failed", str(exc2), source="audio_control")
        else:
            CoInitialize()
            initialized = True
    except Exception as exc:
        logger.warning("COM init failed: %s", exc)
        log_issue("PHX-AUD-020", "com_init_failed", str(exc), source="audio_control")
    if not initialized:
        raise RuntimeError("COM initialization failed")
    try:
        yield
    finally:
        try:
            CoUninitialize()
        except Exception:
            pass


def _get_endpoint(direction: str) -> Any:
    _ensure()
    if direction == "input":
        return AudioUtilities.GetMicrophone()
    return AudioUtilities.GetSpeakers()


def _get_endpoint_volume(direction: str) -> Any:
    endpoint = _get_endpoint(direction)
    interface = endpoint.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def _safe_attr(obj: Any, name: str) -> Optional[Any]:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def list_system_devices() -> Dict[str, Any]:
    if not PYCAW_AVAILABLE:
        return {
            "available": False,
            "devices": [],
            "default_output": None,
            "default_input": None,
        }

    try:
        with _com_session():
            devices: List[Dict[str, Any]] = []
            for device in AudioUtilities.GetAllDevices():
                data_flow = _safe_attr(device, "data_flow")
                if data_flow is None:
                    data_flow = _safe_attr(device, "DataFlow")
                state = _safe_attr(device, "State")
                devices.append(
                    {
                        "id": _safe_attr(device, "id"),
                        "name": _safe_attr(device, "FriendlyName"),
                        "state": int(state) if isinstance(state, int) else state,
                        "data_flow": str(data_flow) if data_flow is not None else None,
                    }
                )

            default_output = None
            default_input = None
            try:
                default_output = AudioUtilities.GetSpeakers().id
            except Exception:
                logger.info("Default output device not available")
            try:
                default_input = AudioUtilities.GetMicrophone().id
            except Exception:
                logger.info("Default input device not available")

        return {
            "available": True,
            "devices": devices,
            "default_output": default_output,
            "default_input": default_input,
        }
    except Exception as exc:
        logger.warning("list_system_devices failed: %s", exc)
        log_issue("PHX-AUD-021", "list_system_devices_failed", str(exc), source="audio_control")
        return {
            "available": False,
            "devices": [],
            "default_output": None,
            "default_input": None,
            "error": str(exc),
        }


def get_master_state(direction: str = "output") -> Dict[str, Any]:
    if not PYCAW_AVAILABLE:
        return {"available": False, "volume": None, "mute": None, "direction": direction}
    try:
        with _com_session():
            volume_control = _get_endpoint_volume(direction)
            return {
                "available": True,
                "volume": float(volume_control.GetMasterVolumeLevelScalar()),
                "mute": bool(volume_control.GetMute()),
                "direction": direction,
            }
    except Exception as exc:
        logger.warning("get_master_state failed: %s", exc)
        log_issue("PHX-AUD-022", "get_master_state_failed", str(exc), source="audio_control")
        return {
            "available": False,
            "volume": None,
            "mute": None,
            "direction": direction,
            "error": str(exc),
        }


def set_master_state(
    direction: str = "output",
    volume: Optional[float] = None,
    mute: Optional[bool] = None,
) -> Dict[str, Any]:
    if not PYCAW_AVAILABLE:
        return {"available": False, "volume": None, "mute": None, "direction": direction}
    try:
        with _com_session():
            volume_control = _get_endpoint_volume(direction)
            if volume is not None:
                volume_control.SetMasterVolumeLevelScalar(float(volume), None)
            if mute is not None:
                volume_control.SetMute(int(bool(mute)), None)
            return get_master_state(direction)
    except Exception as exc:
        logger.warning("set_master_state failed: %s", exc)
        log_issue("PHX-AUD-023", "set_master_state_failed", str(exc), source="audio_control")
        return {
            "available": False,
            "volume": None,
            "mute": None,
            "direction": direction,
            "error": str(exc),
        }


def _session_name(session: Any) -> str:
    name = None
    try:
        name = session.DisplayName
    except Exception:
        name = None
    if not name:
        try:
            name = session._ctl.GetDisplayName()
        except Exception:
            name = None
    if not name and session.Process is not None:
        try:
            name = session.Process.name()
        except Exception:
            name = None
    return name or "System Sounds"


def _session_id(session: Any, index: int) -> str:
    try:
        return session._ctl.GetSessionIdentifier()
    except Exception:
        pass
    if session.Process is not None:
        try:
            return f"pid:{session.Process.pid}"
        except Exception:
            pass
    return f"session:{index}"


def list_sessions() -> Dict[str, Any]:
    if not PYCAW_AVAILABLE:
        return {"available": False, "sessions": []}

    try:
        with _com_session():
            sessions_out: List[Dict[str, Any]] = []
            for index, session in enumerate(AudioUtilities.GetAllSessions()):
                simple = session.SimpleAudioVolume
                pid = None
                if session.Process is not None:
                    try:
                        pid = session.Process.pid
                    except Exception:
                        pid = None
                sessions_out.append(
                    {
                        "id": _session_id(session, index),
                        "name": _session_name(session),
                        "pid": pid,
                        "volume": float(simple.GetMasterVolume()),
                        "mute": bool(simple.GetMute()),
                    }
                )
            return {"available": True, "sessions": sessions_out}
    except Exception as exc:
        logger.warning("list_sessions failed: %s", exc)
        log_issue("PHX-AUD-024", "list_sessions_failed", str(exc), source="audio_control")
        return {"available": False, "sessions": [], "error": str(exc)}


def set_session_state(
    session_id: str,
    volume: Optional[float] = None,
    mute: Optional[bool] = None,
) -> bool:
    if not PYCAW_AVAILABLE:
        return False

    try:
        with _com_session():
            target = session_id.lower()
            for index, session in enumerate(AudioUtilities.GetAllSessions()):
                current_id = _session_id(session, index).lower()
                pid = None
                if session.Process is not None:
                    try:
                        pid = session.Process.pid
                    except Exception:
                        pid = None
                pid_id = f"pid:{pid}" if pid is not None else None

                if target in (current_id, pid_id):
                    simple = session.SimpleAudioVolume
                    if volume is not None:
                        simple.SetMasterVolume(float(volume), None)
                    if mute is not None:
                        simple.SetMute(int(bool(mute)), None)
                    return True
            return False
    except Exception as exc:
        logger.warning("set_session_state failed: %s", exc)
        log_issue("PHX-AUD-025", "set_session_state_failed", str(exc), source="audio_control")
        return False
