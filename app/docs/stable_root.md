# Stable Root Workflow (`G:\Bjorgsun-26`)

- `G:\Bjorgsun-26` is the canonical runtime mirror on the mounted secure drive (VHD stored at `C:\\BjorgProj\\Bjorgsun-26v1.vhdx`, mounted as `G:`).
- Dev repo lives at `G:\Bjorgsun-26\app`. Secrets in `.env` files from the dev repo or `G:\Bjorgsun-26` are loaded automatically alongside the stable root.

## Deploying Updates

```powershell
cd G:\Bjorgsun-26\app
powershell -ExecutionPolicy Bypass -File tools\sync_release.ps1
```

- The sync script copies the code-centric directories plus curated root files into the stable root without touching archives or logs.
- Add `-Source` / `-Target` overrides if you need to point at another drive.

## Launching Everything

- Stable mode: double-click `G:\Bjorgsun-26\server_start.bat` (hidden consoles, UI only).
- Dev mode: use `server_start_dev.bat` for per-service consoles when debugging.
- Desktop shortcuts: `CONTROLS\run_stable.ps1` and `CONTROLS\run_dev.ps1` wrap those launchers. `CONTROLS\gotosleep.ps1` stops Bjorgsun-related processes originating from `G:\Bjorgsun-26` or `G:\Bjorgsun-26\app`.

If the script warns about a missing virtualenv, run `.venv\Scripts\activate && pip install -r requirements.txt` inside `G:\Bjorgsun-26`.

## Extra Notes

- Add more env locations via `BJORG_ENV_ADDITIONAL` (semicolon-delimited file paths).
- `BJORG_STABLE_ROOT` overrides the default `G:\Bjorgsun-26` path if you migrate again.
- Track progress/live feed in `progress_status.txt` so the UI ticker has data to show.
