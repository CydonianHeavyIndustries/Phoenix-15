import logging
import requests
import colorsys

RAZER_SESSION = {"uri": None, "sessionid": None}


def _rgb_to_bgr_int(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def register() -> bool:
    if RAZER_SESSION.get("uri"):
        return True
    try:
        payload = {
            "title": "Bjorgsun-26",
            "description": "Bjorgsun-26 lighting bridge",
            "author": {"name": "Bjorgsun", "contact": "local"},
            "device_supported": ["keyboard", "mouse", "mousepad", "headset", "keypad", "chromalink"],
            "category": "application",
        }
        resp = requests.post("http://localhost:54235/razer/chromasdk", json=payload, timeout=2)
        if resp.status_code != 200:
            logging.error("Razer register failed %s %s", resp.status_code, resp.text)
            return False
        data = resp.json()
        RAZER_SESSION["uri"] = data.get("uri")
        RAZER_SESSION["sessionid"] = data.get("sessionid")
        logging.info("Razer session registered %s", RAZER_SESSION["uri"])
        return True
    except Exception as exc:
        logging.error("Razer register exception: %s", exc)
        return False


def set_static(color: tuple[int, int, int], devices: list[str] | None = None) -> bool:
    if not register():
        return False
    uri = RAZER_SESSION.get("uri")
    if not uri:
        return False
    ok = True
    devs = devices or ["keyboard", "mouse", "mousepad", "headset", "chromalink"]
    payload = {"effect": "CHROMA_STATIC", "param": {"color": _rgb_to_bgr_int(color)}}
    for dev in devs:
        try:
            resp = requests.put(f"{uri}/{dev}", json=payload, timeout=2)
            if resp.status_code != 200:
                logging.error("Razer set %s failed %s %s", dev, resp.status_code, resp.text)
                ok = False
        except Exception as exc:
            logging.error("Razer set %s exception %s", dev, exc)
            ok = False
    return ok


def hue_from_hz(hz: float, amp: float = 1.0) -> tuple[int, int, int]:
    hue = int((hz % 1200) / 1200 * 360)
    r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue / 360, 1, min(1.0, 0.4 + amp * 0.6))]
    return r, g, b
