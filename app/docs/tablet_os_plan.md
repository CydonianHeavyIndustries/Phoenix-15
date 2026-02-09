# Tablet Hub & Custom OS Plan

## Current Hardware Snapshot

Captured via `adb` while the tablet was connected:

| Field | Value |
| --- | --- |
| Brand | `samsung` |
| Model | `SM-T560NU` |
| Codename | `gtelwifiue` |
| Android | `7.1.1` (SDK 25) |
| Build ID | `NMF26X.T560NUUEU1CQK2` |
| ABI | `armeabi-v7a` |
| Hardware | `qcom` |
| /data storage | 12 GB total, 5.4 GB used, 6.1 GB free |

This is a Galaxy Tab E (9.6") Wi-Fi variant. Bootloader unlock + TWRP builds exist, so we can reflash.

## Roadmap

1. **Bootloader & Recovery**
   - Pull Samsung firmware + PIT, unlock bootloader, flash TWRP or custom recovery.
   - Back up the existing partitions for rollback.

2. **Custom OS Build**
   - Fork the LineageOS device tree for `gtelwifiue` (Android 13 target).
   - Integrate minimal Google services or microG if we need Play authentication.
   - Add our own boot animation + branding (“Bjorgsun Tablet Hub”).

3. **Tablet Runtime Stack**
   - Bundle Python 3.11 (Termux or embedded) with a lean Bjorgsun runtime subset (`core/`, `systems/voice`, `ui/tablet`).
   - Include on-device speech (faster-whisper-small) + a small local LLM (e.g., Phi-3-mini) for offline cognition.
   - Provide a WebSocket/gRPC bridge to the PC so the tablet acts as control surface when tethered.

4. **Dock Prompt**
   - `systems/tablet_ops.py` writes `data/tablet_prompt.json` when the tablet shows up on USB.
   - PC UI reads that file and opens a modal: “Choose Stable or Dev”.
   - Tablet app mirrors the same choice, defaulting to Stable if neither side votes within 30 seconds.

5. **Failover Personality**
   - Keep persona + memories synced in `/sdcard/Bjorgsun-sync`.
   - When the tablet runs standalone, it loads the same persona config and exposes an always-on HUD (voice + touch interface).
   - When tethered, it switches to “hybrid” mode: PC handles heavy GPT, tablet mirrors UI and sensor telemetry.

## Immediate Next Steps

1. Finish the stubbed tablet agent + hook it into the UI (prompt overlay).
2. Draft UX mockups for the tablet launcher (Stable vs Dev selection, status view).
3. Prepare the LineageOS build environment and track dependencies (Android build tools, device tree).
4. Package a minimal Bjorgsun runtime for Termux + verify offline TTS/LLM bundles can fit within 6 GB free space.

This document will evolve as we move through flashing, runtime integration, and final UI polish.
