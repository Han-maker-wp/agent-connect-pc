"""Build reproducible AgentConnect-PC controller distributions.

Usage:
  python build_controller.py --clean

The script expects PyInstaller in .build-venv. It creates two onedir
folders under release-staging/ and zips them for GitHub Releases.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYINSTALLER = ROOT / ".build-venv" / "Scripts" / "pyinstaller.exe"
STAGING = ROOT / "release-staging"
DIST = ROOT / "dist" / "controller"
BUILD = ROOT / "build" / "controller"


def run(args: list[str]) -> None:
    print("+", " ".join(str(x) for x in args))
    subprocess.run(args, cwd=ROOT, check=True)


def zip_dir(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--target-exe", type=Path, default=None,
                        help="受控端 windows-mcp-server.exe 的本地路径")
    args = parser.parse_args()
    if not PYINSTALLER.is_file():
        print("[ERROR] Missing .build-venv/Scripts/pyinstaller.exe", file=sys.stderr)
        return 1
    if args.clean:
        for path in (DIST, BUILD, STAGING):
            shutil.rmtree(path, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    run([str(ROOT / ".build-venv" / "Scripts" / "python.exe"), "-m", "compileall", "-q", "agent_connect"])
    specs = [("agent-connect-cli.spec", "agent-connect-cli"), ("agent-connect-gui.spec", "agent-connect-gui")]
    for spec, _name in specs:
        run([str(PYINSTALLER), "--noconfirm", "--clean", "--distpath", str(DIST),
             "--workpath", str(BUILD), str(ROOT / "packaging" / spec)])
    source_exe = args.target_exe.resolve() if args.target_exe else ROOT / "windows-mcp-server.exe"
    if not source_exe.is_file() and not args.target_exe:
        source_exe = ROOT / "dist" / "windows-mcp-server.exe"
    if not source_exe.is_file() and not args.target_exe:
        source_exe = ROOT / "release-assets" / "windows-mcp-server.exe"
    if not source_exe.is_file():
        raise FileNotFoundError(
            "受控端 windows-mcp-server.exe 不存在；请从 GitHub Release 下载，"
            "放入 release-assets/，或用 --target-exe 指定路径。"
        )
    for name in ("agent-connect-cli", "agent-connect-gui"):
        package = STAGING / name
        shutil.rmtree(package, ignore_errors=True)
        package.mkdir(parents=True, exist_ok=True)
        built_exe = DIST / f"{name}.exe"
        if not built_exe.is_file():
            raise FileNotFoundError(f"PyInstaller output missing: {built_exe}")
        shutil.copy2(built_exe, package / f"{name}.exe")
        if source_exe.is_file():
            shutil.copy2(source_exe, package / "windows-mcp-server.exe")
        for template in ("install_windows_mcp.bat", "uninstall_windows_mcp.bat", "fix_tailscale_template.bat"):
            source = ROOT / template
            if source.is_file():
                shutil.copy2(source, package / template)
        for doc in ("README.md", "README.en.md", "AGENTS.md", "LICENSE"):
            source = ROOT / doc
            if source.is_file():
                shutil.copy2(source, package / doc)
        zip_dir(package, STAGING / f"{name}-windows-x64.zip")
    print(f"[PASS] Release assets: {STAGING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
