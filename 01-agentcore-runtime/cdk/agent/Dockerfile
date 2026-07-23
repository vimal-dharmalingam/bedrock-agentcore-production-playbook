# Same pattern validated in manual-container-build/Dockerfile. CDK's fromAsset() just runs
# `docker build` on this directory (with --platform linux/arm64, set via Platform.LINUX_ARM64
# in cdk_stack.py) -- it's still real Docker underneath, so the same QEMU-emulation gotcha
# applies, and the same fix (pre-fetch wheels on the host, don't pip install inside the
# emulated container) carries over unchanged.

FROM python:3.13-slim

WORKDIR /app

# Dependencies pre-downloaded on the HOST as arm64 wheels before running `cdk deploy`:
#   uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 \
#       --target vendor --only-binary=:all: -r requirements.txt
# (run from inside this agent/ folder) -- then just copied in, no pip install at build time.
COPY vendor/ /app/vendor/
ENV PYTHONPATH=/app/vendor

# Required so the bedrock_agentcore SDK's server binds 0.0.0.0 instead of 127.0.0.1 --
# without this, the container looks healthy but every external request gets an empty reply.
ENV DOCKER_CONTAINER=1

COPY my_calc_agent.py .

EXPOSE 8080

CMD ["python", "my_calc_agent.py"]
