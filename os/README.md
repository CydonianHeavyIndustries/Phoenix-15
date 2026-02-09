# Phoenix-15 USB OS (Debian 12)

This folder builds a bootable Debian 12 (Bookworm) ISO that boots straight into the Phoenix-15 UI on a minimal desktop. The OS runs from the USB and avoids internal disks unless the user explicitly opts in.

## What You Get
- Debian 12 live ISO (hybrid UEFI + legacy BIOS).
- Minimal desktop (XFCE + LightDM auto-login).
- Phoenix-15 backend + UI server as systemd services.
- Chromium kiosk launch as the primary interface.
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
1) Install Docker or live-build on WSL.
2) Run:
   `bash os/build_iso.sh`

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

First-boot UX notes are captured in:
`os/FIRST_BOOT.md`

## Notes
- This ISO is intended to be installed or run entirely from USB.
- The Phoenix UI is the primary interface; desktop remains minimal.
