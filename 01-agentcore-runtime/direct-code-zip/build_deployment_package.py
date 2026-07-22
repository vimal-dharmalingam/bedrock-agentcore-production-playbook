"""
Builds deployment_package.zip for AgentCore Runtime direct code deployment.

What this does, step by step:
1. Installs this folder's requirements.txt into a local `deployment_package/` folder --
   specifically the Linux/arm64 build of each package, using `uv pip install
   --python-platform aarch64-manylinux2014 --only-binary=:all:`. This works fine from
   Windows: uv just downloads the matching pre-built wheel files, no actual compilation
   or Linux machine needed, since --only-binary refuses source-only packages.
2. Zips deployment_package/*'s contents plus my_calc_agent.py into deployment_package.zip,
   explicitly setting standard Linux file permissions (644 files / 755 dirs) on every entry.
   This matters because AgentCore Runtime enforces POSIX permissions on the unzipped files,
   and a zip built on Windows doesn't set these by default -- skipping this step is a common
   cause of deploy failures that isn't obvious from the error message.

Run this from inside 01-agentcore-runtime/direct-code-zip/:
    python build_deployment_package.py

Safe to rerun -- wipes and rebuilds deployment_package/ and the zip each time.
"""
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
BUILD_DIR = FOLDER / "deployment_package"
ZIP_PATH = FOLDER / "deployment_package.zip"
ENTRYPOINT_FILE = FOLDER / "my_calc_agent.py"
REQUIREMENTS_FILE = FOLDER / "requirements.txt"

PYTHON_VERSION = "3.13"


def install_dependencies():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()

    print(f"Installing dependencies for linux/arm64, Python {PYTHON_VERSION}...")
    subprocess.run(
        [
            "uv", "pip", "install",
            "--python-platform", "aarch64-manylinux2014",
            "--python-version", PYTHON_VERSION,
            "--target", str(BUILD_DIR),
            "--only-binary", ":all:",
            "-r", str(REQUIREMENTS_FILE),
        ],
        check=True,
    )


def add_file_with_unix_permissions(zf: zipfile.ZipFile, filepath: Path, arcname: str):
    """Adds a file to the zip with explicit 644 permissions, regardless of host OS."""
    zi = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
    zi.external_attr = (0o644 | stat.S_IFREG) << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    with open(filepath, "rb") as f:
        zf.writestr(zi, f.read())


def build_zip():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    print(f"Building {ZIP_PATH.name}...")
    with zipfile.ZipFile(ZIP_PATH, "w") as zf:
        # Installed dependencies go at the root of the zip (mirrors /var/task at runtime)
        for path in BUILD_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                arcname = str(path.relative_to(BUILD_DIR))
                add_file_with_unix_permissions(zf, path, arcname)

        # Entrypoint file also goes at the root
        add_file_with_unix_permissions(zf, ENTRYPOINT_FILE, ENTRYPOINT_FILE.name)

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Done: {ZIP_PATH} ({size_mb:.1f} MB)")
    if size_mb > 250:
        print("WARNING: exceeds the 250MB zipped limit for direct code deployment.")


if __name__ == "__main__":
    try:
        install_dependencies()
    except FileNotFoundError:
        print("'uv' not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)
    build_zip()
