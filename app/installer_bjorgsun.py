"""
Single-file installer for Bjorgsun-26.

When built with PyInstaller --onefile and the payload data bundled, this will:
- Prompt for install path (default G:\Bjorgsun-26)
- Prompt for launcher choice: both / stable / dev
- Copy the bundled payload (dist/Bjorgsun-26 folder + Bjorgsun-26.exe + launch scripts)
- Create desktop shortcuts for the chosen launchers
- Drop an uninstall script into the install directory
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def implied_base() -> Path:
    """Return the directory where bundled payload lives (PyInstaller-aware)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent


def read_choice(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
        return val or default
    except Exception:
        return default


def read_tri(prompt: str, default: str = "later") -> str:
    """Return one of yes/no/later."""
    val = read_choice(prompt + " [yes/no/later] ", default).lower()
    if val not in {"yes", "no", "later"}:
        return default
    return val


def require_agreement():
    """Display legal notice and 26 explicit rules; require affirmative consent."""
    notice = """
LEGAL NOTICE / USER RESPONSIBILITY / HOSTING CONSENT
- This software is provided with good intentions. You are solely responsible for how you deploy or use it.
- If the software misbehaves, acts autonomously, or is modified, you accept all liability and consequences.
- The author bears no responsibility for improper, malicious, or harmful use by you or others.
- By continuing, you agree your device may act as a host/server for AI modules you configure. You are responsible for network exposure, security, data handling, and compliance with laws/policies.
- You may NOT sell, resell, license, or otherwise monetize this program or the ideas in it. Any unauthorized sale grants the author the right to pursue $90,000,000 CAD in damages.
"""
    rules = [
        "Use only for lawful and ethical purposes.",
        "Do not use for harassment, abuse, or intimidation.",
        "Do not use for violence or physical harm.",
        "Do not use for self-harm encouragement.",
        "Do not use for discrimination or hate.",
        "Do not use for misinformation or disinformation.",
        "Do not use to violate privacy or spy unlawfully.",
        "Do not use for unauthorized surveillance.",
        "Do not use for fraud, scams, or theft.",
        "Do not use for malware or exploits.",
        "Do not use for unauthorized system access.",
        "Do not use for data exfiltration.",
        "Do not use for impersonation without consent.",
        "Do not use for deepfakes without consent.",
        "Do not use for doxxing or exposing private info.",
        "Do not use for mass unsolicited messages.",
        "Do not use for plagiarism or IP theft.",
        "Do not use to bypass safety controls.",
        "Do not weaponize outputs or models.",
        "Protect minors and vulnerable groups.",
        "Obey local laws and platform policies.",
        "Keep logs and audit trails where required.",
        "Secure API keys, tokens, and user data.",
        "Obtain consent for recording/monitoring.",
        "Disclose AI use when applicable.",
        "If unsure, stop and seek legal/ethical review.",
        "Do not sell, resell, or monetize this software or its ideas without explicit written permission; violation allows a $90,000,000 CAD claim.",
    ]
    print(notice.strip())
    resp = read_choice("Type I ACCEPT to continue, or anything else to exit: ", "")
    if resp.strip() != "I ACCEPT":
        print("Installation aborted (agreement not accepted).")
        sys.exit(1)
    print("\nPlease acknowledge each rule (type I AGREE for each).")
    for idx, rule in enumerate(rules, start=1):
        print(f"Rule {idx:02d}: {rule}")
        ans = read_choice("Acknowledge (type I AGREE): ", "")
        if ans.strip() != "I AGREE":
            print(f"Installation aborted on rule {idx}.")
            sys.exit(1)
    resale = read_choice(
        "Explicit resale prohibition: type 'I WILL NOT SELL BJORGSUN' to continue: ", ""
    )
    if resale.strip() != "I WILL NOT SELL BJORGSUN":
        print("Installation aborted (resale clause not accepted).")
        sys.exit(1)
    liability = read_choice(
        "Consent to legal action for unauthorized resale: type 'I ACCEPT LEGAL LIABILITY' to continue: ",
        "",
    )
    if liability.strip() != "I ACCEPT LEGAL LIABILITY":
        print("Installation aborted (legal liability not accepted).")
        sys.exit(1)


def make_shortcut(name: str, target: str, icon: str):
    """Create a desktop shortcut via powershell."""
    try:
        desktop = Path(os.path.join(os.environ["UserProfile"], "Desktop"))
        ps = [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            (
                "$W=New-Object -ComObject WScript.Shell;"
                f"$L=$W.CreateShortcut((Join-Path '{desktop}' '{name}.lnk'));"
                f"$L.TargetPath='{target}';"
                f"if(Test-Path '{icon}'){{$L.IconLocation='{icon}'}};"
                "$L.Save();"
            ),
        ]
        subprocess.run(ps, check=False, capture_output=True)
    except Exception:
        pass


def write_uninstaller(dest: Path):
    """Write a simple uninstall batch script into install dir."""
    script = f"""@echo off
setlocal
chcp 65001 >nul
echo [!] This will remove Bjorgsun-26 from "{dest}". Continue? (Y/N)
set /p ans=
if /I not "%ans%"=="Y" if /I not "%ans%"=="YES" (
  echo Cancelled.
  exit /b 0
)
del /f /q "%UserProfile%\\Desktop\\Bjorgsun Stable.lnk" >nul 2>&1
del /f /q "%UserProfile%\\Desktop\\Bjorgsun Dev.lnk" >nul 2>&1
rmdir /s /q "{dest}" >nul 2>&1
echo [✓] Uninstall complete.
pause
endlocal
"""
    try:
        (dest / "uninstall_bjorgsun.bat").write_text(script, encoding="utf-8")
    except Exception:
        pass


def write_choices(dest: Path, choices: dict):
    """Persist install choices for later reference."""
    try:
        import json

        (dest / "install_choices.json").write_text(
            json.dumps(choices, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def write_env(dest: Path, entries: dict):
    """Write .env with provided entries (blanks if skipped)."""
    lines = [f"{k}={v}" for k, v in entries.items()]
    try:
        (dest / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def copy_payload_with_fallback(
    dest: Path,
    src_dir: Path,
    src_exe: Path,
    launch_stable: Path,
    launch_dev: Path,
    goto_sleep: Path,
    choice: str,
) -> Path:
    """
    Copy payload to dest; if any failure occurs, fall back to the current working directory.
    Returns the directory where files were actually written.
    """
    def _do_copy(target: Path):
        target.mkdir(parents=True, exist_ok=True)
        print(f"[*] Copying payload to {target} ...")
        shutil.copytree(src_dir, target / "dist" / "Bjorgsun-26", dirs_exist_ok=True)
        if src_exe.exists():
            shutil.copy2(src_exe, target / "Bjorgsun-26.exe")
        if launch_stable.exists() and choice in {"both", "stable"}:
            shutil.copy2(launch_stable, target / "launch_stable.bat")
        if launch_dev.exists() and choice in {"both", "dev"}:
            shutil.copy2(launch_dev, target / "launch_dev.bat")
        if goto_sleep.exists():
            shutil.copy2(goto_sleep, target / "Gotosleep.bat")
        return target

    try:
        return _do_copy(dest)
    except Exception as exc:
        fallback = Path.cwd()
        print(f"[!] Copy to {dest} failed: {exc}")
        print(f"[*] Falling back to run directory: {fallback}")
        try:
            return _do_copy(fallback)
        except Exception as exc2:
            print(f"[!] Fallback copy failed: {exc2}")
            sys.exit(1)


def main():
    father_install = False
    try:
        resp = read_choice("Is this the father (owner) install? [y/N]: ", "N").lower()
        father_install = resp in {"y", "yes"}
    except Exception:
        father_install = False
    if not father_install:
        require_agreement()
    else:
        print("Owner install detected. Skipping public user legal gate; owner assumes full liability.")

    # If existing install .env exists, reuse it and skip secrets prompts; also reuse repo .env if present
    existing_env = {}
    for candidate in [
        Path("G:/Bjorgsun-26/.env"),
        Path(__file__).resolve().parent / ".env",
    ]:
        try:
            if candidate.exists():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        existing_env[k.strip()] = v.strip()
        except Exception:
            continue
    base = implied_base()
    payload = base / "payload"

    # Primary (PyInstaller-bundled) payload
    src_dir = payload / "dist" / "Bjorgsun-26"
    src_exe = payload / "Bjorgsun-26.exe"
    launch_stable = payload / "launch_stable.bat"
    launch_dev = payload / "launch_dev.bat"
    goto_sleep = payload / "Gotosleep.bat"

    # Fallback to local dist/ when running from source (no bundled payload)
    if not src_dir.exists():
        repo_root = Path(__file__).resolve().parent
        alt_dir = repo_root / "dist" / "Bjorgsun-26"
        alt_exe = repo_root / "dist" / "Bjorgsun-26.exe"
        alt_launch_stable = repo_root / "launch_stable.bat"
        alt_launch_dev = repo_root / "launch_dev.bat"
        alt_gotosleep = repo_root / "Gotosleep.bat"
        if alt_dir.exists():
            src_dir = alt_dir
            src_exe = alt_exe
            launch_stable = alt_launch_stable
            launch_dev = alt_launch_dev
            goto_sleep = alt_gotosleep
            payload = repo_root  # for logging / shortcuts icon path
        else:
            print("[!] Payload folder missing. Rebuild the installer with payload or ensure dist/ exists.")
            sys.exit(1)

    default_dest = Path("G:/Bjorgsun-26")
    dest_input = read_choice(f"Install path [{default_dest}]: ", str(default_dest))
    dest = Path(dest_input).expanduser()
    choice = read_choice("Install launchers (both/stable/dev) [both]: ", "both").lower()
    if choice not in {"both", "stable", "dev"}:
        choice = "both"

    tablet_choice = read_tri("Would you like to set up a tablet?")
    gpt_choice = read_tri("Would you like to set up GPT/LLM services?")
    ios_choice = read_tri("Would you like to set up iOS/mobile mode?")
    env_choice = read_tri("Configure connections/API keys now?")
    dev_choice = read_tri("Install dev tooling (requires owner password)?")
    dev_pwd = ""
    if dev_choice == "yes":
        dev_pwd = read_choice("Enter owner dev password (DEV_MODE_PASSWORD): ", "")

    dest = copy_payload_with_fallback(
        dest=dest,
        src_dir=src_dir,
        src_exe=src_exe,
        launch_stable=launch_stable,
        launch_dev=launch_dev,
        goto_sleep=goto_sleep,
        choice=choice,
    )

    exe_icon = str(dest / "dist" / "Bjorgsun-26" / "Bjorgsun-26.exe")
    if choice in {"both", "stable"}:
        make_shortcut("Bjorgsun Stable", str(dest / "launch_stable.bat"), exe_icon)
    if choice in {"both", "dev"}:
        make_shortcut("Bjorgsun Dev", str(dest / "launch_dev.bat"), exe_icon)

    write_uninstaller(dest)
    choices = {
        "launchers": choice,
        "tablet": tablet_choice,
        "gpt": gpt_choice,
        "ios": ios_choice,
        "env_choice": env_choice,
    }
    write_choices(dest, choices)

    # Optional env collection
    env_entries = {
        "OPENAI_API_KEY": "",
        "LLM_API_KEY": "",
        "LLM_ENDPOINT": "",
        "DISCORD_TOKEN": "",
        "TITANFALL2_LOG_PATH": "",
        "TITANFALL2_TELEMETRY_FILE": "",
        "DEV_ACCESS_KEY": "",
        "DEV_MODE_PASSWORD": dev_pwd if dev_choice == "yes" else "",
        "FATHER_KEY": "",
        "OWNER_KEY": "",
        "CORPORATE_KEY": "",
        "ENTERPRISE_KEY": "",
        "LEGAL_KEY": "",
        "FRIEND_KEY": "",
        "FAMILY_KEY": "",
        "USER_KEY": "",
        "SPARK_KEY": "",
        "USBMK_KEY": "",
        "FADER_KEY": "",
        "BJORGSUN_KEY": "",
        "MOM_KEY": "",
        "DAD_KEY": "",
        "MAMMOUTH_KEY": "",
        "ZACK_KEY": "",
        "JACK_KEY": "",
        "SPAULDO_KEY": "",
        "JOHN_KEY": "",
        "JEAN_KEY": "",
        "BEURKSON_KEY": "",
        "BJORGSON_KEY": "",
        "CLARA_KEY": "",
        "CHARLOTTE_KEY": "",
        "GUILLAUME_KEY": "",
        "YAN_KEY": "",
        "RESTSWITCH_FILE": r"E:\restswitch.key",
        "FADER_USB_LABEL": "Fader",
        "FADER_SENTINEL_FILE": r"E:\Fader\summon.key",
        "PEER_COORDINATOR_URL": "",
        "PEER_TOKEN": "",
        "OPENAI_SEARCH_MODEL": "gpt-4o-mini",
        "DISCORD_ALERT_WEBHOOK": "",
        "SMTP_HOST": "",
        "SMTP_PORT": "",
        "SMTP_USER": "",
        "SMTP_PASS": "",
        "ALERT_EMAILS": "",
        "SMS_ENABLED": "",
        "TWILIO_SID": "",
        "TWILIO_TOKEN": "",
        "SMS_FROM": "",
        "SMS_TO": "",
    }
    if env_choice == "yes":
        for key in env_entries:
            env_entries[key] = existing_env.get(key, "") or read_choice(
                f"Enter {key} (or leave blank): ", ""
            )
    # Auto-generate secure defaults if blank
    if not env_entries["DEV_ACCESS_KEY"]:
        env_entries["DEV_ACCESS_KEY"] = secrets.token_urlsafe(16)
    # Master keys
    for role in [
        "FATHER_KEY",
        "OWNER_KEY",
        "CORPORATE_KEY",
        "ENTERPRISE_KEY",
        "LEGAL_KEY",
        "FRIEND_KEY",
        "FAMILY_KEY",
        "USER_KEY",
        "SPARK_KEY",
        "USBMK_KEY",
        "FADER_KEY",
        "BJORGSUN_KEY",
        "MOM_KEY",
        "DAD_KEY",
        "MAMMOUTH_KEY",
        "ZACK_KEY",
        "JACK_KEY",
        "SPAULDO_KEY",
        "JOHN_KEY",
        "JEAN_KEY",
        "BEURKSON_KEY",
        "BJORGSON_KEY",
        "CLARA_KEY",
        "CHARLOTTE_KEY",
        "GUILLAUME_KEY",
        "YAN_KEY",
        "PEER_TOKEN",
    ]:
        if not env_entries[role]:
            env_entries[role] = secrets.token_urlsafe(24)
    write_env(dest, env_entries)

    # Trim optional modules if user said "no"
    optional_dirs = {
        "tablet": tablet_choice,
        "ios": ios_choice,
    }
    for opt, resp in optional_dirs.items():
        if resp == "no":
            target = dest / opt
            if target.exists():
                print(f"[*] Removing optional module: {opt}")
                shutil.rmtree(target, ignore_errors=True)

    # Create placeholders for later imports/exports
    try:
        (dest / "imports").mkdir(exist_ok=True)
        (dest / "exports").mkdir(exist_ok=True)
    except Exception:
        pass

    print("[" + "\u2713" + f"] Install complete at {dest}")
    print("Launch: desktop shortcuts or dist/Bjorgsun-26/Bjorgsun-26.exe")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as se:
        # Bubble up clean exits silently; pause on error exits for double-click runs.
        if se.code not in (0, None):
            print(f"[!] Installer exited with code {se.code}.")
            try:
                input("Press Enter to close...")
            except Exception:
                pass
        raise
    except Exception as exc:
        try:
            import traceback

            log_path = Path.cwd() / "installer_error.log"
            log_path.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
            print(f"[!] Installer failed: {exc}")
            print(f"[!] Traceback logged to {log_path}")
        except Exception:
            print(f"[!] Installer failed: {exc}")
        input("Press Enter to close...")



