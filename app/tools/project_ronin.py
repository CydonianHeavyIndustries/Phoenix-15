"""
PROJECT_RONIN - Titanfall 2 mod manager.

Capabilities:
- Configure Titanfall 2 install path (defaults to Steam common path).
- Import a mod folder from anywhere into Northstar mods.
- Import all mods from an r2modman profile.
- Auto-fetch dependencies from Thunderstore when a mod declares them.
- Warn if a mod declares conflicts with already-installed mods.
- Launch modded (Northstar) or vanilla, and launch Bjorgsun (stable) from the same UI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Entry, Frame, Label, StringVar, Text, Tk, filedialog, messagebox
from urllib import error, request

DEFAULT_TF_PATH = Path(r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2")
DEFAULT_R2_PROFILE = Path(r"C:\\Users\\Beurkson\\AppData\\Roaming\\r2modmanPlus-local\\Titanfall2\\profiles\\Default")
CONFIG_DIR = Path(__file__).resolve().parent.parent / "data" / "project_ronin"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.json"

# Bjorgsun stable launcher (uses repo root)
BJORGSUN_ROOT = Path(__file__).resolve().parents[2]
BJORGSUN_LAUNCH = BJORGSUN_ROOT / "server_start.bat"


def _default_config() -> dict:
    return {
        "tf_path": str(DEFAULT_TF_PATH),
        "bjorgsun_launch": str(BJORGSUN_LAUNCH),
        "r2_profile": str(DEFAULT_R2_PROFILE),
    }


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg = _default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def log(text_widget: Text, msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    text_widget.insert(END, f"[{stamp}] {msg}\n")
    text_widget.see(END)


def pick_directory(initial: Path) -> Path | None:
    selected = filedialog.askdirectory(initialdir=str(initial))
    if not selected:
        return None
    return Path(selected)


def copy_mod(src: Path, dst_root: Path, log_ui: Text) -> Path | None:
    if not src.exists():
        log(log_ui, f"Mod path missing: {src}")
        return None
    ensure_dir(dst_root)
    target = dst_root / src.name
    if target.exists():
        target = dst_root / f"{src.name}_import_{int(time.time())}"
    log(log_ui, f"Copying mod to {target} ...")
    shutil.copytree(src, target)
    log(log_ui, "Import complete.")
    return target


def launch_process(exe: Path, cwd: Path | None, args: list[str], log_ui: Text) -> None:
    if not exe.exists():
        messagebox.showerror("Missing file", f"{exe} not found.")
        return
    try:
        subprocess.Popen([str(exe), *args], cwd=str(cwd) if cwd else None)
        log(log_ui, f"Launched: {exe} {' '.join(args)}")
    except Exception as exc:
        messagebox.showerror("Launch failed", str(exc))


def parse_mod_dependencies(mod_dir: Path) -> list[str]:
    mod_json = mod_dir / "mod.json"
    if not mod_json.exists():
        return []
    try:
        data = json.loads(mod_json.read_text(encoding="utf-8"))
        deps = data.get("Dependencies") or data.get("dependencies") or []
        return [d for d in deps if isinstance(d, str) and d.strip()]
    except Exception:
        return []


def is_installed(mods_root: Path, dep_name: str) -> bool:
    dep_lower = dep_name.lower()
    for entry in mods_root.iterdir():
        if entry.is_dir() and entry.name.lower().startswith(dep_lower):
            return True
    return False


def fetch_download_url(namespace: str, name: str, version: str | None) -> str | None:
    base = f"https://thunderstore.io/api/experimental/package/{namespace}/{name}/"
    url = base if not version else base + f"{version}/"
    req = request.Request(url, headers={"User-Agent": "ProjectRonin/1.0"})
    try:
        with request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError:
        return None
    except Exception:
        return None
    if version:
        return data.get("download_url")
    versions = data.get("versions") or []
    if not versions:
        return None
    return versions[0].get("download_url")


def parse_dep_id(dep: str) -> tuple[str, str, str | None] | None:
    parts = dep.split("-")
    if len(parts) < 2:
        return None
    namespace = parts[0]
    name = parts[1]
    version = parts[2] if len(parts) >= 3 else None
    return namespace, name, version


def install_dependency(dep: str, mods_root: Path, log_ui: Text) -> None:
    parsed = parse_dep_id(dep)
    if not parsed:
        log(log_ui, f"[deps] Unknown dep format: {dep}")
        return
    namespace, name, version = parsed
    if is_installed(mods_root, name):
        log(log_ui, f"[deps] Already installed: {name}")
        return
    url = fetch_download_url(namespace, name, version)
    if not url:
        log(log_ui, f"[deps] Download URL not found for {dep}")
        return
    log(log_ui, f"[deps] Downloading {dep} ...")
    try:
        with request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:
        log(log_ui, f"[deps] Download failed: {exc}")
        return
    ensure_dir(mods_root)
    with tempfile.TemporaryDirectory() as td:
        zip_path = Path(td) / f"{name}.zip"
        zip_path.write_bytes(data)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(mods_root)
            log(log_ui, f"[deps] Installed {dep}")
        except Exception as exc:
            log(log_ui, f"[deps] Extract failed: {exc}")


def install_dependencies_for_mod(mod_dir: Path, mods_root: Path, log_ui: Text) -> None:
    deps = parse_mod_dependencies(mod_dir)
    if not deps:
        return
    log(log_ui, f"Checking dependencies for {mod_dir.name}: {deps}")
    for dep in deps:
        install_dependency(dep, mods_root, log_ui)


def read_mod_metadata(mod_dir: Path) -> dict:
    """Return {name, version, conflicts} if mod.json is present."""
    meta = {"name": mod_dir.name, "version": "", "conflicts": []}
    mod_json = mod_dir / "mod.json"
    if not mod_json.exists():
        return meta
    try:
        data = json.loads(mod_json.read_text(encoding="utf-8"))
        meta["name"] = data.get("Name") or data.get("name") or meta["name"]
        meta["version"] = data.get("Version") or data.get("version") or ""
        meta["conflicts"] = data.get("Conflicts") or data.get("conflicts") or []
    except Exception:
        pass
    if not isinstance(meta["conflicts"], list):
        meta["conflicts"] = []
    return meta


def check_compatibility(new_mod: Path, mods_root: Path, log_ui: Text) -> None:
    """Compare declared conflicts against installed mods and warn."""
    new_meta = read_mod_metadata(new_mod)
    conflicts = [c.lower() for c in new_meta["conflicts"] if isinstance(c, str)]
    if not conflicts:
        return
    installed = []
    for mod in mods_root.iterdir():
        if mod.is_dir():
            meta = read_mod_metadata(mod)
            installed.append(meta["name"].lower())
    hit = [c for c in conflicts if c in installed]
    if hit:
        log(log_ui, f"[compat] {new_meta['name']} conflicts with installed mods: {', '.join(hit)}")


def list_profile_mods(profile_dir: Path) -> list[dict]:
    """Return metadata for mods under an r2modman profile."""
    mods: list[dict] = []
    candidates = (
        profile_dir / "R2Northstar" / "mods",
        profile_dir / "R2Northstar" / "plugins",
        profile_dir / "mods",  # fallback
        profile_dir / "BepInEx" / "plugins",  # fallback
    )
    for base in candidates:
        if not base.exists():
            continue
        for mod in base.iterdir():
            if mod.is_dir():
                meta = read_mod_metadata(mod)
                meta["source"] = base.name
                mods.append(meta)
    return mods


def log_mod_list(mods: list[dict], log_ui: Text, label: str = "Installed mods") -> None:
    if not mods:
        log(log_ui, f"[mods] {label}: none found.")
        return
    log(log_ui, f"[mods] {label} ({len(mods)}):")
    for m in mods:
        name = m.get("name", "")
        version = m.get("version", "")
        source = m.get("source", "")
        suffix = f" [{source}]" if source else ""
        log(log_ui, f" - {name} {version}{suffix}")


def import_local_mod(mods_root: Path, log_ui: Text) -> None:
    """Let the user pick a mod archive or folder and import it."""
    ensure_dir(mods_root)
    # Try file first
    file_path = filedialog.askopenfilename(
        title="Select mod archive or folder",
        filetypes=[
            ("Archives", "*.zip;*.tar;*.gz;*.bz2;*.rar;*.7z"),
            ("All files", "*.*"),
        ],
    )
    src: Path | None = None
    is_archive = False
    if file_path:
        src = Path(file_path)
        is_archive = src.suffix.lower() in {".zip", ".tar", ".gz", ".bz2", ".rar", ".7z"}
    else:
        # fall back to directory picker
        dir_path = filedialog.askdirectory(title="Select mod folder")
        if dir_path:
            src = Path(dir_path)
    if not src:
        return

    if is_archive:
        target = mods_root / f"{src.stem}_import_{int(time.time())}"
        ensure_dir(target)
        try:
            shutil.unpack_archive(str(src), str(target))
            log(log_ui, f"Unpacked archive to {target}")
        except Exception as exc:
            log(log_ui, f"[import] Failed to unpack {src.name}: {exc}")
            return
    elif src.is_dir():
        target = copy_mod(src, mods_root, log_ui)
        if not target:
            return
    else:
        log(log_ui, f"[import] Unsupported file: {src}")
        return

    install_dependencies_for_mod(target, mods_root, log_ui)
    check_compatibility(target, mods_root, log_ui)


def sync_r2_to_game(profile_dir: Path, mods_root: Path, log_ui: Text) -> None:
    """Mirror r2modman profile mods into the game mods folder before launch."""
    candidate_dirs = [
        profile_dir / "R2Northstar" / "mods",
        profile_dir / "R2Northstar" / "plugins",
        profile_dir / "mods",  # fallback
        profile_dir / "BepInEx" / "plugins",  # fallback
    ]
    sources = [d for d in candidate_dirs if d.exists()]
    if not sources:
        log(log_ui, f"[r2modman] No mods found under {profile_dir}")
        return
    ensure_dir(mods_root)
    # Backup current mods folder before replacing
    if any(mods_root.iterdir()):
        backup = mods_root.parent / f"_mods_backup_{int(time.time())}"
        try:
            shutil.copytree(mods_root, backup)
            log(log_ui, f"[r2modman] Backup created at {backup}")
        except Exception as exc:
            log(log_ui, f"[r2modman] Backup failed: {exc}")
    # Clean target mods folder
    for item in list(mods_root.iterdir()):
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception as exc:
            log(log_ui, f"[r2modman] Cleanup failed on {item.name}: {exc}")
    # Copy all mods/plugins from the profile into the game mods dir
    for src_root in sources:
        for mod in src_root.iterdir():
            dest = mods_root / mod.name
            try:
                if mod.is_dir():
                    shutil.copytree(mod, dest)
                else:
                    shutil.copy2(mod, dest)
                log(log_ui, f"[r2modman] Deployed {mod.name}")
                if dest.is_dir():
                    install_dependencies_for_mod(dest, mods_root, log_ui)
                    check_compatibility(dest, mods_root, log_ui)
            except Exception as exc:
                log(log_ui, f"[r2modman] Failed to deploy {mod.name}: {exc}")


def toggle_vanilla(tf_path: Path, log_ui: Text) -> None:
    mods_dir = tf_path / "R2Northstar" / "mods"
    disabled = tf_path / "R2Northstar" / "_mods_disabled"
    if mods_dir.exists():
        if disabled.exists():
            shutil.rmtree(disabled, ignore_errors=True)
        log(log_ui, f"Disabling mods -> {disabled}")
        mods_dir.rename(disabled)
    ensure_dir(mods_dir)
    exe = tf_path / "Titanfall2.exe"
    launch_process(exe, tf_path, [], log_ui)


def toggle_modded(tf_path: Path, log_ui: Text) -> None:
    mods_dir = tf_path / "R2Northstar" / "mods"
    disabled = tf_path / "R2Northstar" / "_mods_disabled"
    if disabled.exists() and not mods_dir.exists():
        log(log_ui, "Restoring mods from disabled folder.")
        disabled.rename(mods_dir)
    ensure_dir(mods_dir)
    exe = tf_path / "NorthstarLauncher.exe"
    launch_process(exe, tf_path, [], log_ui)


class RoninUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("PROJECT_RONIN - Titanfall 2 Mod Manager")
        cfg = load_config()
        self.cfg = cfg
        self.tf_path_var = StringVar(value=cfg.get("tf_path", str(DEFAULT_TF_PATH)))
        self.bj_launch_var = StringVar(value=cfg.get("bjorgsun_launch", str(BJORGSUN_LAUNCH)))
        self.r2_profile_var = StringVar(value=cfg.get("r2_profile", str(DEFAULT_R2_PROFILE)))

        top = Frame(root)
        top.pack(fill=BOTH, padx=8, pady=6)

        Label(top, text="Titanfall 2 path:").grid(row=0, column=0, sticky="w")
        Entry(top, textvariable=self.tf_path_var, width=70).grid(row=0, column=1, padx=4)
        Button(top, text="Browse", command=self.pick_tf).grid(row=0, column=2)

        Label(top, text="Bjorgsun stable launcher:").grid(row=1, column=0, sticky="w")
        Entry(top, textvariable=self.bj_launch_var, width=70).grid(row=1, column=1, padx=4)
        Button(top, text="Browse", command=self.pick_bj).grid(row=1, column=2)

        Label(top, text="r2modman profile:").grid(row=2, column=0, sticky="w")
        Entry(top, textvariable=self.r2_profile_var, width=70).grid(row=2, column=1, padx=4)
        Button(top, text="Browse", command=self.pick_r2).grid(row=2, column=2)

        btns = Frame(root)
        btns.pack(fill=BOTH, padx=8, pady=6)
        Button(btns, text="Import Mod", command=self.import_mod, width=16).pack(side=LEFT, padx=4)
        Button(btns, text="Import Local Mods", command=self.import_local, width=18).pack(side=LEFT, padx=4)
        Button(btns, text="Import from r2modman", command=self.import_r2, width=20).pack(side=LEFT, padx=4)
        Button(btns, text="Play Modded (Northstar)", command=self.play_modded, width=22).pack(side=LEFT, padx=4)
        Button(btns, text="Play Vanilla", command=self.play_vanilla, width=14).pack(side=LEFT, padx=4)
        Button(btns, text="List r2modman mods", command=self.list_r2_mods, width=18).pack(side=RIGHT, padx=4)
        Button(btns, text="Launch Bjorgsun (Stable)", command=self.launch_bj, width=22).pack(side=RIGHT, padx=4)

        self.log = Text(root, height=14, wrap="word")
        self.log.pack(fill=BOTH, expand=True, padx=8, pady=6)
        log(self.log, "Ready.")

    def pick_tf(self) -> None:
        current = Path(self.tf_path_var.get())
        chosen = pick_directory(current if current.exists() else DEFAULT_TF_PATH)
        if chosen:
            self.tf_path_var.set(str(chosen))
            self._persist()

    def pick_bj(self) -> None:
        current = Path(self.bj_launch_var.get())
        chosen = filedialog.askopenfilename(
            initialdir=str(current.parent if current.exists() else BJORGSUN_ROOT),
            filetypes=[("Batch files", "*.bat"), ("All files", "*.*")],
        )
        if chosen:
            self.bj_launch_var.set(chosen)
            self._persist()

    def pick_r2(self) -> None:
        current = Path(self.r2_profile_var.get())
        chosen = pick_directory(current if current.exists() else DEFAULT_R2_PROFILE)
        if chosen:
            self.r2_profile_var.set(str(chosen))
            self._persist()

    def import_mod(self) -> None:
        tf_path = Path(self.tf_path_var.get())
        src = pick_directory(tf_path)
        if not src:
            return
        mods_dir = tf_path / "R2Northstar" / "mods"
        target = copy_mod(src, mods_dir, self.log)
        if target:
            install_dependencies_for_mod(target, mods_dir, self.log)
            check_compatibility(target, mods_dir, self.log)

    def import_local(self) -> None:
        tf_path = Path(self.tf_path_var.get())
        mods_dir = tf_path / "R2Northstar" / "mods"
        import_local_mod(mods_dir, self.log)
        self._persist()

    def import_r2(self) -> None:
        tf_path = Path(self.tf_path_var.get())
        profile = Path(self.r2_profile_var.get())
        mods_dir = tf_path / "R2Northstar" / "mods"
        sync_r2_to_game(profile, mods_dir, self.log)
        log_mod_list(list_profile_mods(profile), self.log, "r2modman profile")
        self._persist()

    def play_modded(self) -> None:
        tf_path = Path(self.tf_path_var.get())
        self._persist()
        # Always sync r2modman profile into the game mods before launching
        sync_r2_to_game(Path(self.r2_profile_var.get()), tf_path / "R2Northstar" / "mods", self.log)
        log_mod_list(list_profile_mods(Path(self.r2_profile_var.get())), self.log, "r2modman profile")
        toggle_modded(tf_path, self.log)

    def play_vanilla(self) -> None:
        tf_path = Path(self.tf_path_var.get())
        self._persist()
        toggle_vanilla(tf_path, self.log)

    def launch_bj(self) -> None:
        launcher = Path(self.bj_launch_var.get())
        self._persist()
        launch_process(launcher, launcher.parent if launcher.exists() else None, [], self.log)

    def _persist(self) -> None:
        self.cfg["tf_path"] = self.tf_path_var.get()
        self.cfg["bjorgsun_launch"] = self.bj_launch_var.get()
        self.cfg["r2_profile"] = self.r2_profile_var.get()
        save_config(self.cfg)

    def list_r2_mods(self) -> None:
        profile = Path(self.r2_profile_var.get())
        log_mod_list(list_profile_mods(profile), self.log, "r2modman profile")


def main() -> None:
    root = Tk()
    RoninUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
