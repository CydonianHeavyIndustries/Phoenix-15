# Developer quickstart — Bjorgsun Dev Mode

This file explains the recommended local development flow and the dev-mode launcher.

Quickstart (one-liner)

```powershell
# create venv, install deps, open workspace, and run runtime
.\dev_launch.ps1 -OpenWorkspace
```

Files added

- `BjorgsunDev.code-workspace`: VS Code workspace file. When you open this workspace, the window title will show `Bjorgsun26EXE`.
- `dev_launch.ps1`: opinionated PowerShell launcher. Creates and uses `venv/`, installs `requirements.txt` (unless `-NoDeps`), sets `UI_THEME` env var (default `femboy`), and runs the app.

How to use

- Open the new workspace in VS Code: `code BjorgsunDev.code-workspace` or double-click the file in Explorer.
- From PowerShell (recommended):

```powershell
# in repo root
.\dev_launch.ps1 -OpenWorkspace     # creates venv, installs deps, opens workspace, runs the app
.\dev_launch.ps1 -NoDeps -Theme titanfall  # skip installs, use Titanfall palette
```

Changing the workspace title

- The workspace file `BjorgsunDev.code-workspace` sets the visible name to `Bjorgsun26EXE`. Opening that file in VS Code will show that title instead of "Untitled (Workspace)". This does not alter any files or branches; it's just a local workspace file.

Notes and suggestions

- The launcher sets `UI_THEME` for quick theme switching. See `ui/README.dev.md` for the available theme names.
- If you prefer a different default theme, edit the `-Theme` parameter in `dev_launch.ps1` or set `UI_THEME` in your environment.
- The script will create a `venv/` directory and pip install requirements — if you don't want that, pass `-NoDeps`.
- The workspace file also recommends helpful extensions (Python, Pylance, Jupyter, GitLens, icons, material theme).

If you want a runtime UI theme picker or a persistent preference store, I can add a Preferences panel next — tell me which preset you want selected by default.
