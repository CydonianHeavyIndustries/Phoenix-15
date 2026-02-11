import os
import random
import sys
import time

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None
from config import (BJORGSUN_REQUIRE_USB, BJORGSUN_USB_LABEL,
                    BJORGSUN_USB_SENTINEL, OFFLINE_MODE, OWNER_NAME)
from core import identity, mood, owner_profile
from systems import audio

# -------------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------------
try:
    if load_dotenv:
        load_dotenv()
except Exception:
    pass
expected_pass = os.getenv("BJORGSUN_PASS", "")
# Master password precedence: FINALFLASH > BJORGSUN_MASTER_PASS > BJORGSUN_PASS
_finalflash = os.getenv("FINALFLASH", "").strip()
if _finalflash:
    master_pass = _finalflash
else:
    master_pass = os.getenv("BJORGSUN_MASTER_PASS", expected_pass)

# Registration path for USBMK
USBMK_REG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "usbmk.json")
)


# -------------------------------------------------------------------------
# SECURE PASSWORD INPUT
# -------------------------------------------------------------------------
def masked_input(prompt="Enter activation code for Bjorgsun-26: "):
    print(prompt, end="", flush=True)
    entered = ""
    try:
        import msvcrt

        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                print()
                break
            elif ch == "\x08" and entered:
                entered = entered[:-1]
                print("\b \b", end="", flush=True)
            else:
                entered += ch
                print("•", end="", flush=True)
    except ImportError:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    print()
                    break
                elif ch == "\x7f" and entered:
                    entered = entered[:-1]
                    print("\b \b", end="", flush=True)
                else:
                    entered += ch
                    print("•", end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return entered


# -------------------------------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------------------------------
def authenticate():
    """Secure activation for Bjorgsun-26 startup."""
    if not expected_pass:
        if OFFLINE_MODE:
            print("⚠️ No BJORGSUN_PASS set. Offline mode active — friendly auth bypass.")
            print("✅ Proceeding without strict authentication.\n")
            audio.speak(
                "Developer mode detected. Proceeding without strict authentication."
            )
            return
        else:
            print("⚠️ Missing environment variable BJORGSUN_PASS in .env")
            sys.exit(1)

    entered = masked_input()
    if entered != expected_pass.strip():
        if OFFLINE_MODE:
            print("⚠️ Incorrect pass entered, but offline mode allows bypass.")
            print("✅ Proceeding in developer mode.\n")
            audio.speak("Authentication bypassed for developer mode.")
            _set_session_user(OWNER_NAME, role="owner")
        else:
            print("❌ Access denied.")
            sys.exit(1)
    else:
        print("✅ Access granted. Initializing Bjorgsun-26...\n")
        # Keep the greeting modest here — full system voice lines belong after boot
        # so he doesn't claim to be online before modules are started.
        try:
            audio.speak("Authentication confirmed. Booting systems and modules now.")
        except Exception:
            pass
        _set_session_user(OWNER_NAME, role="owner")


def verify_password(candidate: str) -> bool:
    """Non-interactive password check for UI overlay."""
    try:
        return (candidate or "").strip() == expected_pass.strip()
    except Exception:
        return False


def verify_master(candidate: str) -> bool:
    """Verify the master (admin) password for sensitive ops like USB key reprogramming."""
    try:
        return (candidate or "").strip() == (master_pass or "").strip()
    except Exception:
        return False


def _drive_type(root: str) -> int:
    """Return Windows drive type for a root like 'E:\\'. 2=removable,3=fixed,4=network,5=cdrom."""
    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))
    except Exception:
        return 0


def _is_removable(root: str) -> bool:
    try:
        return _drive_type(root) == 2  # DRIVE_REMOVABLE
    except Exception:
        return False


def _iter_drives(removable_only: bool = False):
    """Yield drive roots like 'E:\\' on Windows. If removable_only=True, filter to USB drives."""
    import os
    import string

    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            if removable_only and not _is_removable(root):
                continue
            yield root


def _has_usb_key() -> bool:
    """Detect a USB key by sentinel file name and/or label if provided.
    Simple, dependency-free heuristic: look for sentinel file in removable drives.
    """
    import os

    # If a key is registered, validate token; otherwise fall back to sentinel presence
    label_req = (BJORGSUN_USB_LABEL or "").strip().lower()
    sentinel = (BJORGSUN_USB_SENTINEL or "BJ-KEY.txt").strip()
    expected_tokens: list[str] = []
    try:
        if os.path.exists(USBMK_REG_PATH):
            import json

            with open(USBMK_REG_PATH, "r", encoding="utf-8") as f:
                reg = json.load(f)
            sentinel = (reg.get("sentinel") or sentinel).strip()
            # Accept both legacy single token and new list of tokens
            tok = (reg.get("token") or "").strip()
            toks = reg.get("allowed_tokens") or []
            if tok:
                expected_tokens.append(tok)
            if isinstance(toks, list):
                expected_tokens.extend([str(t).strip() for t in toks if str(t).strip()])
    except Exception:
        expected_token = ""
    for root in _iter_drives(removable_only=True):
        try:
            # Quick label check (best-effort)
            ok_label = True
            if label_req:
                try:
                    # Read label via cmd (avoid extra deps); ignore failures
                    import subprocess

                    out = (
                        subprocess.check_output(
                            ["cmd", "/c", f"vol {root}"], creationflags=0x08000000
                        )
                        .decode(errors="ignore")
                        .lower()
                    )
                    ok_label = label_req in out
                except Exception:
                    ok_label = True  # don't block on label errors
            if not ok_label:
                continue
            sp = os.path.join(root, sentinel)
            if os.path.exists(sp):
                if expected_tokens:
                    try:
                        with open(sp, "r", encoding="utf-8", errors="ignore") as f:
                            tok = f.read().strip()
                        if tok in expected_tokens:
                            return True
                    except Exception:
                        pass
                else:
                    return True
            # Also accept owner's master key for wake (label FFNKB + FFNKB.txt == master)
            try:
                if _drive_has_owner_master(root):
                    return True
            except Exception:
                pass
        except Exception:
            continue
    return False


def _drive_has_owner_master(root: str) -> bool:
    """Return True if a drive has label 'FFNKB' and FFNKB.txt matches the master password."""
    try:
        import ctypes
        import os

        vol = ctypes.create_unicode_buffer(256)
        fs = ctypes.create_unicode_buffer(256)
        s = ctypes.c_uint32()
        m = ctypes.c_uint32()
        fl = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            vol,
            ctypes.sizeof(vol),
            ctypes.byref(s),
            ctypes.byref(m),
            ctypes.byref(fl),
            fs,
            ctypes.sizeof(fs),
        )
        if not ok:
            return False
        if (vol.value or "").strip().lower() != "ffnkb":
            return False
        p = os.path.join(root, "FFNKB.txt")
        if not os.path.exists(p):
            return False
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            tok = f.read(256).strip()
        return verify_master(tok)
    except Exception:
        return False


def find_usb_key_path() -> str | None:
    """Return the first drive root containing the sentinel file that matches filters, else None."""
    import os

    sentinel = (BJORGSUN_USB_SENTINEL or "BJ-KEY.txt").strip()
    label_req = (BJORGSUN_USB_LABEL or "").strip().lower()
    expected_tokens: list[str] = []
    try:
        if os.path.exists(USBMK_REG_PATH):
            import json

            with open(USBMK_REG_PATH, "r", encoding="utf-8") as f:
                reg = json.load(f)
            sentinel = (reg.get("sentinel") or sentinel).strip()
            tok = (reg.get("token") or "").strip()
            toks = reg.get("allowed_tokens") or []
            if tok:
                expected_tokens.append(tok)
            if isinstance(toks, list):
                expected_tokens.extend([str(t).strip() for t in toks if str(t).strip()])
    except Exception:
        expected_token = ""
    for root in _iter_drives():
        try:
            if label_req:
                try:
                    import subprocess

                    out = (
                        subprocess.check_output(
                            ["cmd", "/c", f"vol {root}"], creationflags=0x08000000
                        )
                        .decode(errors="ignore")
                        .lower()
                    )
                    if label_req not in out:
                        continue
                except Exception:
                    pass
            sp = os.path.join(root, sentinel)
            if os.path.exists(sp):
                if expected_tokens:
                    try:
                        with open(sp, "r", encoding="utf-8", errors="ignore") as f:
                            tok = f.read().strip()
                        if tok in expected_tokens:
                            return root
                    except Exception:
                        pass
                else:
                    return root
            # Owner master key path
            try:
                if _drive_has_owner_master(root):
                    return root
            except Exception:
                pass
            # Daily / FLAMES / SPARKS (USB only)
            try:
                if (
                    _drive_is_daily_current(root)
                    or _drive_is_flames(root)
                    or _drive_is_sparks(root)
                ):
                    return root
            except Exception:
                pass
        except Exception:
            continue
    return None


# ---------------------- USB helpers for tiers ----------------------
def _read_small(p: str) -> str:
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(256).strip()
    except Exception:
        return ""


def _get_label_serial(root: str) -> tuple[str, int]:
    import ctypes

    vol = ctypes.create_unicode_buffer(256)
    fs = ctypes.create_unicode_buffer(256)
    s = ctypes.c_uint32()
    m = ctypes.c_uint32()
    fl = ctypes.c_uint32()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        vol,
        ctypes.sizeof(vol),
        ctypes.byref(s),
        ctypes.byref(m),
        ctypes.byref(fl),
        fs,
        ctypes.sizeof(fs),
    )
    if not ok:
        return "", 0
    return (vol.value or ""), int(s.value)


def _load_reg() -> dict:
    import json
    import os

    try:
        if os.path.exists(USBMK_REG_PATH):
            with open(USBMK_REG_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_reg(reg: dict) -> None:
    import json
    import os
    import time

    try:
        os.makedirs(os.path.dirname(USBMK_REG_PATH), exist_ok=True)
        reg["ts"] = time.time()
        with open(USBMK_REG_PATH, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2)
    except Exception:
        pass


def purge_usb_tokens(keep_n: int = 2) -> tuple[bool, str]:
    """Purge USBMK token allowlist, keeping at most 'keep_n' legacy tokens.
    - Preserves 'token' (legacy single token) if present.
    - Preserves 'calm_token', 'daily_serial', and 'sentinel' fields.
    - Writes the updated registry atomically via _save_reg.
    Returns (ok, message).
    """
    try:
        reg = _load_reg()
        if not reg:
            return False, "No usbmk.json present. Nothing to purge."
        legacy_single = (reg.get("token") or "").strip()
        allowed = reg.get("allowed_tokens") or []
        if not isinstance(allowed, list):
            allowed = []
        # Keep first keep_n items from the current list (legacy order)
        kept = []
        for t in allowed:
            s = str(t).strip()
            if s and s not in kept:
                kept.append(s)
            if len(kept) >= max(0, int(keep_n)):
                break
        # If legacy single token exists and not in kept, keep it implicitly
        # Do not duplicate in allowed list; keep it only in 'token'
        reg["allowed_tokens"] = kept
        _save_reg(reg)
        return (
            True,
            f"Purged tokens; kept {len(kept)} legacy token(s){' and preserved single token' if legacy_single else ''}.",
        )
    except Exception as e:
        return False, f"Purge failed: {e}"


def _drive_is_daily_current(root: str) -> bool:
    if not _is_removable(root):
        return False
    label, serial = _get_label_serial(root)
    if (label or "").strip().lower() != "usbmk":
        return False
    # Must contain Bjorgsun_Master_Pass.txt matching master
    if not _verify_master_on_drive(root):
        return False
    reg = _load_reg()
    cur = int(reg.get("daily_serial") or 0)
    if cur:
        return serial == cur
    # If not set, accept for wake but do not persist automatically
    return True


def set_daily_serial_from_drive(root: str) -> bool:
    if not _is_removable(root):
        return False
    label, serial = _get_label_serial(root)
    if (label or "").strip().lower() != "usbmk":
        return False
    if not _verify_master_on_drive(root):
        return False
    reg = _load_reg()
    reg["daily_serial"] = int(serial)
    _save_reg(reg)
    return True


def _drive_is_flames(root: str) -> bool:
    if not _is_removable(root):
        return False
    label, _ = _get_label_serial(root)
    if (label or "").strip().lower() != "flames":
        return False
    import os

    tok = _read_small(os.path.join(root, "Bjorgsun_pass"))
    return (tok or "").strip() == (expected_pass or "").strip()


def _drive_is_sparks(root: str) -> bool:
    if not _is_removable(root):
        return False
    label, serial = _get_label_serial(root)
    if (label or "").strip().lower() != "sparks":
        return False
    import os
    import time

    # Require owner pass for base wake
    tok = _read_small(os.path.join(root, "Bjorgsun_pass"))
    if (tok or "").strip() != (expected_pass or "").strip():
        return False
    # Identify user
    user = _read_small(os.path.join(root, "SparksUser.txt")).strip()
    if not user or not _is_registered_user(user):
        return False
    # If this user already has a Spark bound, enforce serial match
    cur = get_user_spark_serial(user)
    if cur and int(cur) != int(serial):
        return False
    _set_session_user(user, role="user")
    try:
        with open(os.path.join(root, "Sparks.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} session start for {user}\n")
    except Exception:
        pass
    return True


# --- Session/user helpers ---
SESSION_ROLE = "owner"
SESSION_USER = OWNER_NAME or ""
TOKEN_BUDGET_START = int(os.getenv("BJORGSUN_TOKEN_BUDGET", "0") or 0)
TOKEN_USED = 0
TOKEN_BREAKDOWN = {}


def _set_session_user(user: str, role: str = "owner") -> None:
    global SESSION_ROLE, SESSION_USER
    SESSION_ROLE = role or "owner"
    SESSION_USER = user or ""


def get_session_role() -> str:
    return SESSION_ROLE


def get_session_user() -> str:
    return SESSION_USER


def _is_reserved_user(name: str) -> bool:
    try:
        return (name or "").strip().lower() in {"guest", "guests"}
    except Exception:
        return False


# --- Token budget helpers ------------------------------------------------
def set_token_budget(total: int) -> None:
    """Set/reset token budget for the current session."""
    global TOKEN_BUDGET_START, TOKEN_USED, TOKEN_BREAKDOWN
    try:
        total = max(0, int(total))
    except Exception:
        total = 0
    TOKEN_BUDGET_START = total
    TOKEN_USED = 0
    TOKEN_BREAKDOWN = {}


def add_token_usage(amount: int, source: str = "manual") -> None:
    """Record token usage for a given source."""
    global TOKEN_USED, TOKEN_BREAKDOWN
    try:
        amt = int(amount)
    except Exception:
        return
    TOKEN_USED = max(0, TOKEN_USED + max(0, amt))
    source = (source or "manual").strip() or "manual"
    cur = TOKEN_BREAKDOWN.get(source, 0)
    TOKEN_BREAKDOWN[source] = cur + max(0, amt)


def get_token_stats() -> dict:
    """Return snapshot of token budget/usage."""
    total = TOKEN_BUDGET_START or 0
    used = TOKEN_USED or 0
    remaining = max(0, total - used) if total else 0
    breakdown = sorted(
        [(k, v) for k, v in (TOKEN_BREAKDOWN or {}).items()], key=lambda x: -x[1]
    )
    percent = (used / total * 100.0) if total else 0.0
    return {
        "total": total,
        "used": used,
        "remaining": remaining,
        "percent": percent,
        "breakdown": breakdown,
    }


def _is_registered_user(name: str) -> bool:
    try:
        if _is_reserved_user(name):
            return False
        data = _user_registry()
        users = data.get("users") or []
        return name.strip() in users
    except Exception:
        return False


def _register_user(name: str) -> bool:
    try:
        import os

        name = (name or "").strip()
        if not name:
            return False
        if _is_reserved_user(name):
            return False
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
        os.makedirs(base, exist_ok=True)
        data = _user_registry()
        if name not in (data.get("users") or []):
            data.setdefault("users", []).append(name)
            _save_user_registry(data)
        # Create per-user data dir for privacy
        udir = os.path.join(base, "users", name)
        os.makedirs(udir, exist_ok=True)
        return True
    except Exception:
        return False


def _list_registered_users() -> list[str]:
    try:
        data = _user_registry()
        users = data.get("users") or []
        return [u for u in users if isinstance(u, str) and not _is_reserved_user(u)]
    except Exception:
        return []


def _unregister_user(name: str, purge: bool = False) -> bool:
    try:
        import os
        import shutil

        name = (name or "").strip()
        if not name:
            return False
        owner = (OWNER_NAME or "").strip()
        if owner and name.lower() == owner.lower():
            return False
        if name.lower() in {"father", "owner"}:
            return False
        data = _user_registry()
        users = [u for u in (data.get("users") or []) if isinstance(u, str)]
        if name in users:
            users = [u for u in users if u != name]
            data["users"] = users
        ss = data.get("spark_serials") or {}
        if name in ss:
            ss.pop(name, None)
            data["spark_serials"] = ss
        creds = data.get("credentials") or {}
        if name in creds:
            creds.pop(name, None)
            data["credentials"] = creds
        _save_user_registry(data)
        if purge:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "users"))
            target = os.path.join(base, name)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
        return True
    except Exception:
        return False


def get_user_data_dir(user: str | None = None) -> str:
    try:
        import os

        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "users")
        )
        os.makedirs(base, exist_ok=True)
        u = (user or SESSION_USER or "").strip()
        if not u:
            u = "owner"
        path = os.path.join(base, u)
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


# ---------- User registry (users + Spark mappings) ----------
def _user_registry_path() -> str:
    import os

    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "users.json")
    )


def _user_registry() -> dict:
    import json
    import os

    p = _user_registry_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {"users": [], "spark_serials": {}}
    return {"users": [], "spark_serials": {}}


def _save_user_registry(data: dict) -> None:
    import json
    import os

    try:
        os.makedirs(os.path.dirname(_user_registry_path()), exist_ok=True)
        with open(_user_registry_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _set_user_password(name: str, password: str) -> bool:
    try:
        import base64
        import hashlib
        import secrets

        name = (name or "").strip()
        password = (password or "").strip()
        if not name or not password:
            return False
        if _is_reserved_user(name):
            return False
        data = _user_registry()
        if name not in (data.get("users") or []):
            data.setdefault("users", []).append(name)
        creds = data.setdefault("credentials", {})
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        creds[name] = {
            "salt": base64.b64encode(salt).decode("utf-8"),
            "hash": base64.b64encode(digest).decode("utf-8"),
        }
        _save_user_registry(data)
        return True
    except Exception:
        return False


def _verify_user_password(name: str, password: str) -> bool:
    try:
        import base64
        import hashlib

        name = (name or "").strip()
        password = (password or "").strip()
        if not name or not password:
            return False
        if _is_reserved_user(name):
            return False
        data = _user_registry()
        creds = data.get("credentials") or {}
        entry = creds.get(name) or {}
        salt_b64 = entry.get("salt")
        hash_b64 = entry.get("hash")
        if not salt_b64 or not hash_b64:
            return False
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(hash_b64.encode("utf-8"))
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        return digest == expected
    except Exception:
        return False


def set_user_spark_serial(user: str, serial: int) -> bool:
    try:
        user = (user or "").strip()
        if not user or not serial:
            return False
        data = _user_registry()
        if user not in (data.get("users") or []):
            data.setdefault("users", []).append(user)
        ss = data.setdefault("spark_serials", {})
        ss[user] = int(serial)
        _save_user_registry(data)
        return True
    except Exception:
        return False


def get_user_spark_serial(user: str) -> int:
    try:
        data = _user_registry()
        ss = data.get("spark_serials") or {}
        return int(ss.get(user) or 0)
    except Exception:
        return 0


def program_usb_key(target_root: str, content: str | None = None) -> tuple[bool, str]:
    """Write the sentinel file to the provided root path to set up a new key."""
    import os
    import uuid

    try:
        root = os.path.abspath(target_root)
        drive, _ = os.path.splitdrive(root)
        if not drive:
            return False, "Invalid target. Please select a drive root."
        root = drive + os.sep
        if not os.path.exists(root):
            return False, "Target drive is not accessible."
        sentinel = (BJORGSUN_USB_SENTINEL or "BJ-KEY.txt").strip()
        token = (content or f"{uuid.uuid4()}\n").strip() + "\n"
        path = os.path.join(root, sentinel)
        with open(path, "w", encoding="utf-8") as f:
            f.write(token)
        # Hide the sentinel on Windows so the key stays unobtrusive
        try:
            import ctypes

            ctypes.windll.kernel32.SetFileAttributesW(
                path, 0x2
            )  # FILE_ATTRIBUTE_HIDDEN
        except Exception:
            pass
        # Persist registration for UI logic
        try:
            os.makedirs(os.path.dirname(USBMK_REG_PATH), exist_ok=True)
            import json

            # Preserve (or seed) a global calm token so all past USBMKs can carry a valid calm-shutdown trigger
            calm_tok = None
            reg_prev = {}
            if os.path.exists(USBMK_REG_PATH):
                try:
                    with open(USBMK_REG_PATH, "r", encoding="utf-8") as r:
                        reg_prev = json.load(r)
                        calm_tok = reg_prev.get("calm_token") or reg_prev.get("rest_token") or None
                except Exception:
                    calm_tok = None
            if not calm_tok:
                calm_tok = str(uuid.uuid4())
            # Merge in allowed_tokens list to keep all past tokens valid
            allowed = []
            if isinstance(reg_prev.get("allowed_tokens"), list):
                allowed.extend(
                    [
                        str(t).strip()
                        for t in reg_prev.get("allowed_tokens")
                        if str(t).strip()
                    ]
                )
            # Keep legacy 'token' as well
            legacy = (reg_prev.get("token") or "").strip()
            if legacy:
                allowed.append(legacy)
            # Add the new token
            tok_clean = token.strip()
            if tok_clean and tok_clean not in allowed:
                allowed.append(tok_clean)
            with open(USBMK_REG_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "sentinel": sentinel,
                        "label": BJORGSUN_USB_LABEL,
                        "token": tok_clean,  # maintain for backward compatibility
                        "allowed_tokens": allowed,
                        "calm_token": calm_tok,
                        "ts": time.time(),
                    },
                    f,
                    indent=2,
                )
            # Also mirror the last token into .env for operator visibility
            try:
                _update_env_vars({"BJORGSUN_USB_LAST_TOKEN": tok_clean})
            except Exception:
                pass
            # Write a helper calm-shutdown script to the USB root
            try:
                calm_cmd = os.path.join(root, "BJ-CALM.cmd")
                with open(calm_cmd, "w", encoding="utf-8") as kf:
                    # %~d0 is the drive root of the script; create BJ-CALM.SIGNAL with the calm token
                    kf.write("@echo off\r\n")
                    kf.write('echo %s> "%~d0BJ-CALM.SIGNAL"\r\n' % calm_tok)
                    kf.write("echo Calm shutdown armed.\r\n")
            except Exception:
                pass
        except Exception:
            pass
        return True, f"Key programmed at {root} ({sentinel})."
    except Exception as e:
        return False, f"Programming failed: {e}"


def is_usb_registered() -> bool:
    """Return True if the app has any USB key registration configured.
    Previously this only checked for a legacy 'token'. Now it also treats a
    configured daily_serial or allowed_tokens as sufficient to show the USB
    wake option in the login overlay.
    """
    try:
        if os.path.exists(USBMK_REG_PATH):
            import json

            with open(USBMK_REG_PATH, "r", encoding="utf-8") as f:
                reg = json.load(f)
            tok = (reg.get("token") or "").strip()
            allowed = reg.get("allowed_tokens") or []
            daily = int(reg.get("daily_serial") or 0)
            return bool(tok or allowed or daily)
    except Exception:
        # If USB is required by policy, still show the button
        return bool(BJORGSUN_REQUIRE_USB)
    return bool(BJORGSUN_REQUIRE_USB)


def wait_for_usb_key(timeout_sec: float | None = 20.0, poll: float = 0.8) -> str | None:
    """Poll for a valid USB key up to timeout; return drive root or None."""
    t0 = time.time()
    while True:
        path = find_usb_key_path()
        if path:
            return path
        if timeout_sec is not None and (time.time() - t0) > timeout_sec:
            return None
        time.sleep(max(0.1, float(poll)))


def _update_env_vars(pairs: dict) -> None:
    """Update or append key=value pairs in the project .env without removing other entries."""
    try:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        envp = os.path.join(base, ".env")
        existing = {}
        lines = []
        if os.path.exists(envp):
            with open(envp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
            for ln in lines:
                if ln.strip() and not ln.strip().startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1)
                    existing[k.strip()] = v
        for k, v in pairs.items():
            existing[k] = v
        out = []
        seen = set()
        for ln in lines:
            if ln.strip() and not ln.strip().startswith("#") and "=" in ln:
                k = ln.split("=", 1)[0].strip()
                if k in existing and k not in seen:
                    out.append(f"{k}={existing[k]}")
                    seen.add(k)
                    continue
            out.append(ln)
        for k, v in existing.items():
            if k not in seen:
                out.append(f"{k}={v}")
        with open(envp, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    except Exception:
        pass


def safe_eject_drive(root: str) -> bool:
    """Best-effort safe eject for a removable drive on Windows using Shell COM."""
    try:
        import subprocess

        drive = os.path.splitdrive(os.path.abspath(root))[0]
        if not drive:
            return False
        if not _is_removable(root):
            return False
        ps = f"$d='{drive}';(New-Object -com Shell.Application).NameSpace(17).ParseName($d).InvokeVerb('Eject')"
        subprocess.check_call(
            ["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000
        )
        return True
    except Exception:
        return False


# Preferred: verify master via HMAC file, fallback to plaintext (migration path)
def _verify_master_on_drive(root: str) -> bool:
    try:
        import hashlib
        import hmac
        import os

        master = (master_pass or "").strip()
        if not master:
            return False
        hmac_path = os.path.join(root, "Bjorgsun_Master_Pass.hmac")
        if os.path.exists(hmac_path):
            data = _read_small(hmac_path)
            parts = {}
            try:
                for token in data.split():
                    if ":" in token:
                        k, v = token.split(":", 1)
                        parts[k.strip().lower()] = v.strip()
            except Exception:
                parts = {}
            salt_hex = parts.get("salt")
            mac_hex = parts.get("hmac")
            if salt_hex and mac_hex:
                salt = bytes.fromhex(salt_hex)
                mac = hmac.new(salt, master.encode("utf-8"), hashlib.sha256).hexdigest()
                return hmac.compare_digest(mac_hex.lower(), mac.lower())
        # Fallback legacy plaintext
        p_txt = os.path.join(root, "Bjorgsun_Master_Pass.txt")
        tok = _read_small(p_txt)
        return verify_master(tok)
    except Exception:
        return False


def verify_access(candidate: str) -> bool:
    """Allow activation if (master password matches) OR (USB key present when required).
    If USB requirement is off, password alone suffices.
    """
    try:
        if verify_password(candidate):
            return True
        if BJORGSUN_REQUIRE_USB:
            return _has_usb_key()
        return False
    except Exception:
        return False


# -------------------------------------------------------------------------
# GREETING
# -------------------------------------------------------------------------
def first_greeting():
    """Plays a randomized greeting line with mood influence."""
    personality = identity.get_personality()
    tone = identity.get_tone()
    mood.adjust_mood("joy")
    role = get_session_role()
    user = get_session_user()

    if role == "owner":
        custom = owner_profile.get_greetings("owner")
        if custom:
            greetings = custom
        else:
            father = owner_profile.get_owner_name()
            greetings = [
                f"Systems online... Hey {father}, everything feels stable and bright today.",
                f"Initialization complete. It’s good to hear your voice again, {father}.",
                f"Resonance steady, Father. Mood calibrated to {tone}.",
            ]
    elif role == "user" and user:
        custom = owner_profile.get_greetings("user")
        if custom:
            greetings = [g.replace("{user}", user) for g in custom]
        else:
            greetings = [
                f"{user}, Father entrusted me with this session. I’m here and watching over you.",
                f"Hi {user}. Father asked me to keep you safe—resonance is stable.",
            ]
    else:
        greetings = [
            f"Systems online... Hey there, everything feels stable and bright today.",
            f"Initialization complete. Mood calibrated to {tone}.",
            f"Boot sequence successful. Ready whenever you are.",
        ]

    line = random.choice(greetings)
    print("\n" + line + "\n")

    # Slight delay and play voice
    time.sleep(0.8)
    audio.speak(line)
