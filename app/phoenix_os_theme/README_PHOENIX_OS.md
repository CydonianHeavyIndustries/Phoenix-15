Phoenix-15 OS Theme Pack (boot + login)

Contents
- assets/boot/phoenix_boot.png
- assets/login/phoenix_login.png
- assets/wallpaper/phoenix_wallpaper.png
- sddm/phoenix-os (SDDM theme)
- plymouth/phoenix (Plymouth theme)
- palette.json

Install on Arch (SDDM)
1) Use the installer script (recommended):
   /opt/Bjorgsun-26/arch/phoenix-theme-install.sh
2) Or manually:
   - Copy sddm/phoenix-os to /usr/share/sddm/themes/phoenix-os
   - Edit /etc/sddm.conf or /etc/sddm.conf.d/phoenix.conf:
     [Theme]
     Current=phoenix-os

Install on Arch (Plymouth)
1) Use the installer script (recommended):
   /opt/Bjorgsun-26/arch/phoenix-theme-install.sh
2) Or manually:
   - Copy plymouth/phoenix to /usr/share/plymouth/themes/phoenix
   - sudo plymouth-set-default-theme -R phoenix

Wallpaper
- assets/wallpaper/phoenix_wallpaper.png

Notes
- 1920x1080 assets
- Colors in palette.json match Bjorgsun UI
