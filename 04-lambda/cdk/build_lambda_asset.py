"""
Prepares the folder that CDK's `lambda.Code.from_asset()` will zip up and upload as this
function's code. CDK can do dependency bundling itself via a Docker-based build step, but
that's unnecessary complexity for a simple Lambda -- we already know how to prefetch wheels
by hand (same trick from every 01-agentcore-runtime container module, just targeting
x86_64 instead of arm64 since plain Lambda doesn't force arm64). Simpler to reuse that than
to introduce CDK-managed Docker bundling for something this small.

Run from inside 04-lambda/cdk/, before `cdk synth`/`cdk deploy`:
    python build_lambda_asset.py

Safe to rerun -- wipes and rebuilds the build/ folder each time.
"""
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
SRC_DIR = FOLDER / "lambda_src"
BUILD_DIR = FOLDER / "build"
REQUIREMENTS_FILE = SRC_DIR / "requirements.txt"

PYTHON_VERSION = "3.13"


def main():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()

    print(f"Installing dependencies for linux/x86_64, Python {PYTHON_VERSION}...")
    try:
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
    except FileNotFoundError:
        print("'uv' not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)

    shutil.copy(SRC_DIR / "lambda_function.py", BUILD_DIR / "lambda_function.py")
    print(f"Build folder ready: {BUILD_DIR}")


if __name__ == "__main__":
    main()
