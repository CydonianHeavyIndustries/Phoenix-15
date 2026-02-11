# Phoenix-15 USB OS (Ubuntu 24.04)

This folder builds a bootable Ubuntu 24.04 (Noble) ISO that boots straight into the Phoenix-15 UI on a minimal desktop. The OS runs from the USB and avoids internal disks unless the user explicitly opts in.

## What You Get
- Ubuntu 24.04 live ISO (hybrid UEFI + legacy BIOS).
- Minimal desktop (XFCE + LightDM auto-login).
- Phoenix-15 backend + UI server as systemd services.
- Chromium kiosk launch as the primary interface.
- Automatic hardware balancing (CPU affinity + GPU env hints) for backend/UI.
- Optional installer (Calamares) for a wizard-style setup.
- Optional data partition (`PHX_DATA`, exFAT) that Windows can read/write.
- Internal disks are not mounted by default; opt-in via policy file.

## Build the ISO (Windows + Docker)
1) Install Docker Desktop.
2) Run:
   `os\\build_iso.ps1`
3) ISO output:
   `os\\out\\phoenix-15.iso`

## Build the ISO (WSL/Linux)
1) Install Docker or live-build on WSL/Ubuntu.
2) Run:
   `bash os/build_iso_ubuntu.sh`

## Flash to USB
- Use Rufus or Balena Etcher to write `phoenix-15.iso` to the USB.
- Boot from the USB (UEFI/Legacy both supported).

## Optional Data Partition (Windows-accessible)
To keep Phoenix data accessible from Windows:
1) After flashing the ISO, open Disk Management.
2) Create a second partition labeled `PHX_DATA` (exFAT).
3) Phoenix will mount it at `/phoenix-data` on boot.

Optional update folder (Windows-visible):
`PHX_DATA:\phoenix_update`
Contents here will sync into `/opt/phoenix/app` on boot.

## Portable Mode (Run Without Booting)
You can run Phoenix-15 directly from the USB on a host OS:
`portable/README.md`

## Internal Disk Access Policy
By default, the OS does not mount internal disks.
Policy file (Windows-accessible when `PHX_DATA` is present):
`/phoenix-data/phoenix/storage_policy.json`

Set:
`"allow_internal_mounts": true`
to allow internal disk mounts.

## Installer Wizard
Calamares is included for a GUI install flow.
It can be launched from the desktop menu as "Install Phoenix-15".

## Full Disk Install (Wipe + Install)
For a full wipe install from the live USB:
```
sudo phoenix-disk-install.sh --disk /dev/sdX --execute
```
Replace `/dev/sdX` with the target disk (FULL WIPE).

First-boot UX notes are captured in:
`os/FIRST_BOOT.md`

## Notes
- This ISO is intended to be installed or run entirely from USB.
- The Phoenix UI is the primary interface; desktop remains minimal.
- Hardware balance policy: `/etc/phoenix/hardware_policy.json` (default `gpu_mode: balanced`).
- App downloads: `Phoenix App Downloader` launcher or `/usr/local/bin/phoenix-app-download.sh`.
- Game server helper: `/usr/local/bin/phoenix-game-server.sh` (SteamCMD install + templates).
- USB zip updates: `/usr/local/bin/phoenix-update-from-usb.sh` (Apply app updates from a zip on USB).
- Security center: `/usr/local/bin/phoenix-security-center.sh` (firewall, antivirus, quarantine, live protection).
- Integrity check: `/usr/local/bin/phoenix-integrity-check.sh`.
- Offline docs: `/usr/local/bin/phoenix-offline-docs.sh`.
- Network safe mode: `/usr/local/bin/phoenix-network-safe.sh`.
- System control: `Phoenix Control Center` launcher or `/usr/local/bin/phoenix-control-center.sh`.
- LLM bootstrap: `/usr/local/bin/phoenix-firstboot-llm.sh` (first boot), model from `OLLAMA_BOOT_MODEL` in `/etc/phoenix/phoenix.env`.
