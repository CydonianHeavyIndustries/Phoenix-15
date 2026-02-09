## UI theming and quick presets

This file documents how to change the HUD theme for local development.

Built-in presets

- `default` — original Bjorgsun classic teal/cyan palette.
- `femboy` — pink/cyan pastel accents for a softer, playful look.
- `titanfall` — industrial blue + orange highlights, inspired by mech/vehicle HUDs.
- `scifi` — neon purple/teal cyberpunk/sci-fi accents.

How to set a theme

- Environment variable (PowerShell):

```powershell
$env:UI_THEME = 'femboy'
python -m runtime.main
```

- Programmatically (from Python):

```py
from ui import theme
theme.set_theme('titanfall')
# then construct and show your UI (or reapply ttk styles)
```

Notes

- `set_theme` updates the `ui.theme.COLORS` dict in-place so existing code that reads `COLORS` will pick up the change.
- `ui.theme.apply_ttk_theme(root)` still uses the `COLORS` values; call it after changing theme if you have a running root window.
- If you want a custom skin, put images/fonts under `ui/skins/MySkin`.

Suggestions for further polish

- Provide a small launcher or UI toggle to pick themes at runtime and save a preference (e.g., to `~/.bjorgsunrc`).
- Add a light/dark pair for accessibility (increase contrast for text).
