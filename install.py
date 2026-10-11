#!/usr/bin/env python3
"""Copy only manifest-listed files into a NEW explicit local prefix. No downloads."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def install(prefix):
    source = Path(__file__).resolve().parent
    destination = Path(prefix).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("prefix already exists; choose a new directory")
    if source == destination.resolve() or source in destination.resolve().parents:
        raise ValueError("prefix must be outside source package")
    manifest = json.loads((source / "MODULE.json").read_text(encoding="utf-8"))
    files = manifest["publish_files"]
    if not isinstance(files, list) or not files or len(set(files)) != len(files):
        raise ValueError("invalid publication whitelist")
    for name in files:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("unsafe publication path")
        current = source / path
        if not current.is_file() or any((source / Path(*path.parts[:i])).is_symlink()
                                        for i in range(1, len(path.parts) + 1)):
            raise ValueError("missing or symlinked whitelisted file")
    destination.mkdir(parents=True, exist_ok=False)
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    binary_dir = destination / "bin"
    binary_dir.mkdir()
    launcher = binary_dir / "competitor-offer-radar"
    launcher.write_text("#!/usr/bin/env python3\nimport runpy\nfrom pathlib import Path\n"
                        "runpy.run_path(str(Path(__file__).resolve().parents[1] / 'competitor_offer_radar.py'), run_name='__main__')\n",
                        encoding="utf-8")
    launcher.chmod(0o755)
    (binary_dir / "competitor-offer-radar.cmd").write_bytes(
        '@echo off\r\npython "%~dp0..\\competitor_offer_radar.py" %*\r\n'.encode("utf-8"))
    return {"ok": True, "installed_prefix": str(destination), "files_copied": len(files),
            "command": str(launcher), "onboarding": "explicit command only", "network": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install an offline CLI into a new explicit prefix; never change system PATH.")
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.prefix), ensure_ascii=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"ok": False, "error": "installation failed; prefix must be new and manifest valid; inspect partial prefix if created"}))
        sys.exit(2)
