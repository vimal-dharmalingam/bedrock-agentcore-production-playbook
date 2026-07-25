"""
Builds deployment_package.zip for a plain Lambda zip deployment.

Deliberate simplification vs every 01-agentcore-runtime container-based module: AgentCore
Runtime only runs on arm64, forcing the whole vendor/ prefetch + QEMU-avoidance dance. Lambda
supports x86_64 OR arm64 natively -- choosing x86_64 here means no Docker at all, and no
architecture mismatch drama, since x86_64 Linux wheels are what most packages ship by default
anyway. The lesson that still applies: wheels have to match Lambda's LINUX runtime, not your
Windows machine, so we still use uv with --python-platform, just targeting x86_64 instead of
aarch64 this time.

Also note: no `bedrock-agentcore` package in requirements.txt at all -- that SDK is specific to
AgentCore Runtime's HTTP-server hosting model, which plain Lambda doesn't use. boto3 isn't
listed either -- Lambda's Python runtime ships with boto3 preinstalled, unlike AgentCore
Runtime's custom container which has to bring its own.

Run from inside 04-lambda/zip-deploy/:
    python build_lambda_package.py

Safe to rerun -- wipes and rebuilds each time.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
BUILD_DIR = FOLDER / "build"
ZIP_PATH = FOLDER / "deployment_package.zip"
HANDLER_FILE = FOLDER / "lambda_function.py"
REQUIREMENTS_FILE = FOLDER / "requirements.txt"

PYTHON_VERSION = "3.13"


def install_dependencies():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()

    print(f"Installing dependencies for linux/x86_64, Python {PYTHON_VERSION}...")
    subprocess.run(
        [
            "uv", "pip", "install",
            "--python-platform", "x86_64-manylinux2014",
            "--python-version", PYTHON_VERSION,
            "--target", str(BUILD_DIR),
            "--only-binary", ":all:",
            "-r", str(REQUIREMENTS_FILE),
        ],
        check=True,
    )


def build_zip():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    print(f"Building {ZIP_PATH.name}...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in BUILD_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                zf.write(path, path.relative_to(BUILD_DIR))
        # Handler goes at the zip root too -- Lambda's handler setting
        # ("lambda_function.lambda_handler") expects to import it directly.
        zf.write(HANDLER_FILE, HANDLER_FILE.name)

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Done: {ZIP_PATH} ({size_mb:.1f} MB)")
    if size_mb > 50:
        print("WARNING: exceeds the 50MB direct-upload limit -- would need S3 upload instead.")


if __name__ == "__main__":
    try:
        install_dependencies()
    except FileNotFoundError:
        print("'uv' not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)
    build_zip()
