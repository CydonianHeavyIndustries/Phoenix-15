# Phoenix-15 Portable Mode

This lets you run Phoenix-15 from the USB without booting the USB OS.
Use the same USB for either:
- Booting the Phoenix OS, or
- Running the Phoenix app locally on the host OS.

## Main launcher (Windows)
- `RUN_PHOENIX_15.bat` (recommended "whole project" launcher)
  - You can point the desktop shortcut `E:\OneDrive\Desktop\Phoenix-15.lnk` at this file.

## Windows
1) Plug in the USB.
2) Run:
   `portable\\windows\\run_phoenix.bat`

If this is the first run on a new machine:
   `portable\\windows\\setup_venv.bat`

Other Windows launchers:
- `app\\launch_phoenix.bat` (full local stack, includes Ollama checks)
- `app\\run_tray.bat` (tray controller for background runs)

### Auto-start on USB insert (Windows)
Optional, one-time per host PC:
1) Plug in the USB.
2) Run:
   `portable\\windows\\enable_autostart.bat`
   (Windows blocks USB autorun; this installs a per-user logon watcher.)

To remove it later:
   `portable\\windows\\disable_autostart.bat`

## Linux
1) Plug in the USB.
2) Run:
   `portable/linux/run_phoenix.sh`

If this is the first run on a new machine:
   `portable/linux/setup_venv.sh`

## Notes
- The UI build must exist at `app/ui/scifiaihud/build`.
- Logs write to `app/logs/portable_*`.
- For truly portable Windows runs, place the embeddable Python runtime at:
  `portable/runtime/python/python.exe`
- The default power/exit action triggers a safe shutdown and shows a
  "Safe to disconnect Phoenix-15." prompt once it is safe to unplug.
