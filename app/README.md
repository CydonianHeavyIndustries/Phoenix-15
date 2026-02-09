# Bjorgsun-26

Calm, operator-focused AI assistant with dual Stable/Dev UIs, safety rails, device pairing, USB master keys, and alerting. This repo contains the Windows desktop build, installer, and server/runtime pieces.

## Quick Start (Dev)
1) Clone and create venv: `py -3.11 -m venv venv && venv\Scripts\pip install -r requirements.txt && venv\Scripts\pip install -r server\requirements.txt`
2) Run headless launcher: `run_bjorgsun.bat` (menu: Stable/Dev/Sleep). If `.env` is missing, the setup wizard will prompt for keys.
3) Installer from source (no EXE): `venv\Scripts\python.exe installer_bjorgsun.py` (copies payload from `dist/`).

## Key Features
- Stable & Dev UIs (Dev has Tron console, token budget/usage dashboard).
- Pairing, peer heartbeats, OpenAI search endpoint (gated by dev key).
- Alerts: Discord webhook, email, SMS/voice (Twilio), severity routing.
- USBMK tooling (with explicit consent prompts for programming and wipes).
- Tablet pairing, module opt-ins, and lore/import flows.
- Owner/father keys, rest switch placeholders, login overlay with username capture.
- Dev tools: password-gated dev console (via `DEV_MODE_PASSWORD`), module import/export (zip/folder) and VS Code launcher (uses `code` in PATH). Base model ships without extra modules; extensions can be added/approved later.

## Security & Secrets
- `.env` and `.env.*` are ignored. Do **not** commit secrets.
- Before pushing: run secret scanning (e.g., `gitleaks detect --redact` or GitHub Advanced Security secret scanning) and remove any API keys or lore data.
- Audit third-party licenses for any bundled models/assets and comply with their terms.

## Virtual Drive (safe storage)
- A helper script will be added to create/mount an encrypted/isolated virtual drive; user chooses path/letter/name and it enforces double confirmation. Use it to store keys/lore safely.

## USB Safety
- Programming master/Spark keys: requires explicit consent and master password.
- Wipe/format: double confirmation; only allowed on removable drives; quick NTFS format; logs results.

## Legal / EULA
- Draft short-form EULA in `docs/EULA.md` (Canada/Québec focus). Pre-download click-through recommended; in-app installer enforces acceptance.
- No resale/monetization without written permission. Users accept all liability for deployments.

## Branch / Repo
- Main dev branch: `main`. New clean mirror: `https://github.com/Beurkson/Bjorgsun-26.git` (set as default once populated).
- Set upstream after cloning: `git remote add origin https://github.com/Beurkson/Bjorgsun-26.git` then `git push -u origin main`.

## Build
```
run_bjorgsun.bat        # launcher + venv bootstrap + wizard
build_all.bat           # PyInstaller onefile/onedir + installer (large)
```

## Contributing
- Keep secrets out of commits; use sample env templates.
- Prefer fast-forward/squash merges to keep history clean. Avoid merging “dump” branches directly into main.
## License

Copyright (c) 2025 Beurkson. All rights reserved.

Bjorgsun-26 is **source-available**, not open source in the OSI sense.

The code in this repository is released under the **Bjorgsun-26 Non-Commercial
Source License v1.0**:

- You may **view, study, and modify** the source code.
- You may **run** Bjorgsun-26 for your own **personal or internal use**.
- You may **not sell, resell, license, sublicense, rent, lease, or otherwise
  monetize** Bjorgsun-26 or any derivative work **without prior written
  permission** from the author.
- You may **not offer** Bjorgsun-26 (or any derivative) as a paid or
  ad-supported product or service (including SaaS / hosted deployments) without
  a separate signed commercial agreement.
- Any redistribution must keep this notice and the full `LICENSE` file intact.

For full terms, see the `LICENSE` file in this repository.

### Commercial use

Any commercial use of Bjorgsun-26 or derivative works **requires a separate
written commercial license** from the author.

To discuss commercial licensing, contact:  
`<cydonianheavyindustries@gmail.com>`

### Binaries / installer

Prebuilt binaries or installers for Windows or other platforms are governed by
the `docs/EULA.md` click-through agreement in addition to the `LICENSE` file.
By installing or running Bjorgsun-26 from an installer, you agree to the EULA
and the non-commercial licensing terms above.
