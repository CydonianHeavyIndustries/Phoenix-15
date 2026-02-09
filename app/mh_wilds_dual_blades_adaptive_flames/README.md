Dual Blades Adaptive Flames (Monster Hunter Wilds)

Goal
- Demon Mode: warm orange/yellow flames.
- Archdemon Mode: blue/cyan flames (hotter, brighter look).
- "Adaptive" feel by using distinct VFX assets per mode and (if available) stronger effects for higher-intensity moves.

Folder layout
- modinfo.ini: Fluffy Mod Manager metadata.
- natives/: place the game VFX asset overrides here.
- docs/: notes for mapping and workflow.
- palettes/: color palettes for recolor targets.

How to use with Fluffy Mod Manager
1) In Fluffy Mod Manager, pick Monster Hunter Wilds and open the Mods folder.
2) Copy this entire folder into that Mods folder.
3) When you have the correct VFX files, place them under natives/ with the exact same internal path as the game files.

Important: the correct subfolder under natives/ can vary by RE Engine game.
Common examples:
- natives/x64/...
- natives/STM/...
Check your extractor tool or existing mods for the correct platform folder.

What we need next
- Identify the exact VFX assets used by Dual Blades in Demon Mode and Archdemon Mode.
- Record those paths in docs/vfx_mapping.md.
- Replace textures or effect params using your modding tool, then drop the modified files into natives/.

Notes
- If Demon and Archdemon share the same asset, we will need an alternative approach (script/hook) to make them distinct.
- If separate assets are used, we can make Demon warm and Archdemon blue without runtime logic.
