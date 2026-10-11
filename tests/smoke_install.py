"""Cross-platform synthetic installation check. No credentials or network calls.

The CI runner downloads its interpreter/actions; this script itself only uses
local files and processes. Run with: python -B tests/smoke_install.py
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, cwd, expected=0):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               PYTHONIOENCODING="utf-8")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                            encoding="utf-8", timeout=90)
    require(result.returncode == expected,
            "command failed: {}\n{}\n{}".format(command, result.stdout, result.stderr))
    return result


def data(command, cwd, expected=0):
    result = run(command, cwd, expected)
    require(not result.stderr, "unexpected stderr: " + result.stderr)
    return json.loads(result.stdout)


def native_command(prefix, *args):
    if os.name == "nt":
        # Only trusted generated paths and fixed synthetic test arguments reach
        # cmd.exe. Test the distributed .cmd, not a Python-only substitute.
        launcher = prefix / "bin" / "competitor-offer-radar.cmd"
        command = '""{}" {}"'.format(launcher, subprocess.list2cmdline(list(args)))
        # Pass one command line on Windows: re-quoting this as a final argv
        # item would add CRT backslash escapes that cmd.exe does not use.
        interpreter = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c"]
        return subprocess.list2cmdline(interpreter) + " " + command
    return [str(prefix / "bin" / "competitor-offer-radar"), *args]


def main():
    manifest = json.loads((ROOT / "MODULE.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="offer-radar-ci-") as temporary:
        outside = Path(temporary)
        # Spaces deliberately exercise quoting in the real Windows launcher.
        prefix = outside / "installed пакет"
        cwd = outside / "different каталог"
        cwd.mkdir()
        installed = data([sys.executable, "-B", str(ROOT / "install.py"),
                          "--prefix", str(prefix)], cwd)
        require(installed["ok"], "installer did not complete")
        for name in manifest["publish_files"]:
            require((prefix / name).read_bytes() == (ROOT / name).read_bytes(),
                    "installed bytes differ: " + name)
        # Repeated installation must refuse an existing prefix.
        again = data([sys.executable, "-B", str(ROOT / "install.py"),
                      "--prefix", str(prefix)], cwd, expected=2)
        require(again["ok"] is False, "existing prefix was not refused")
        doctor = data(native_command(prefix, "doctor"), cwd)
        require(doctor["ok"] and doctor["mode"] == "offline", "doctor failed")
        require(doctor["network"] is False and doctor["telemetry"] is False,
                "offline contract changed")
        before = str(prefix / "examples" / "before.json")
        after = str(prefix / "examples" / "after.json")
        for path in (before, after):
            require(data(native_command(prefix, "validate", path), cwd)["synthetic"],
                    "fixture must be synthetic")
        report = data(native_command(prefix, "compare", before, after), cwd)
        require(report["ok"] and report["synthetic"], "comparison failed")
        row = next(item for item in report["offers"] if item["id"] == "strategy-session")
        require(row["price"]["absolute_change"] == "2500" and
                row["price"]["percent_change"] == "25", "price calculation differs")
        require(row["delivery"]["absolute_change"] == "2" and
                row["delivery"]["percent_change"] == "50", "duration differs")
        require(row["price"]["scope_changed_warning"] is True,
                "changed bundle warning missing")
        normal = json.dumps(report, ensure_ascii=False)
        require("lookatsoul" not in normal and "lookatshow.ru" not in normal,
                "ordinary JSON contains advertising")
        state = str(outside / "chosen state")
        first = data(native_command(prefix, "onboard", "--state-dir", state), cwd)
        second = data(native_command(prefix, "onboard", "--state-dir", state), cwd)
        require(first["already_shown"] is False and
                "https://t.me/lookatsoul" in first["message"], "first greeting missing")
        require(second["already_shown"] is True and "message" not in second,
                "greeting repeated")
        tests = run([sys.executable, "-B", "-m", "unittest", "discover",
                     "-s", str(prefix / "tests"), "-v"], cwd)
        require("OK" in tests.stderr, "installed regression suite did not complete")
        # Captured bytes are stable across OS; no personal paths in the summary.
        print(json.dumps({"ok": True, "platform": platform.system(),
                          "architecture": platform.machine(),
                          "python": platform.python_version(),
                          "files_verified": len(manifest["publish_files"]),
                          "native_launcher": ".cmd" if os.name == "nt" else "POSIX",
                          "source_and_install_separate": True,
                          "synthetic": True, "ordinary_json_ad_free": True,
                          "onboarding_once": True,
                          "report_sha256": hashlib.sha256(normal.encode("utf-8")).hexdigest()},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
