# Phoenix-15 USB (Arch) - Installer + Data Model

Goal:
- Boot from a small **Installer USB** (Arch ISO).
- Install Phoenix-15 to the **internal SSD**.
- Use a separate **Data USB** for assistant/user data.

Why:
- Windows remains untouched and default.
- Phoenix-15 data stays portable and isolated.

USB Roles:
1) Installer USB (Arch ISO) - bootable installer only.
2) Data USB (PHOENIX_DATA) - exFAT, portable user + assistant data.

---
## Prepare USBs (Windows)
1) Create the **Installer USB** with Rufus (Arch ISO).
2) Format the **Data USB** as exFAT with label: `PHOENIX_DATA`.
3) Copy the project to the Data USB:
   - Folder path (recommended):
     `PHOENIX_TRANSFER/Bjorgsun-26`

---
## Install Phoenix-15 to SSD (from Installer USB)
1) Boot from the Installer USB.
2) Plug in the **Data USB** (PHOENIX_DATA).
3) Open terminal and run:

   lsblk -f
   (Find your SSD root + EFI partitions.)

4) Run the installer script from the copied repo:
   cd /run/media/arch/PHOENIX_DATA/PHOENIX_TRANSFER/Bjorgsun-26/arch
   sudo bash phoenix-ssd-install.sh

The script will:
- Install Arch + XFCE + SDDM
- Apply Phoenix-15 theme (login + boot)
- Copy Bjorgsun-26 repo to /opt/Bjorgsun-26
- Create Phoenix Space data mount at /phoenix-data
- Configure boot menu with Windows default

---
## After Install (first boot)
1) Boot Phoenix-15 from boot menu.
2) Ensure Data USB is plugged in.
3) Run:
   /opt/Bjorgsun-26/arch/phoenix-run.sh

Optional autostart:
   mkdir -p ~/.config/autostart
   cp /opt/Bjorgsun-26/arch/phoenix-autostart.desktop ~/.config/autostart/

Notes:
- Windows partitions are NOT auto-mounted.
- Data USB is mounted at: `/phoenix-data`
- Bjorgsun app data will live on the Data USB.
