# Hand-written Dockerfile (vs starter-toolkit-cli's auto-generated one) so every layer is
# something we chose on purpose, not something `agentcore configure` decided for us.

# python:3.13-slim is a multi-arch image (has both amd64 and arm64 variants under one tag).
# When we build with `docker build --platform linux/arm64`, Docker pulls the arm64 variant --
# no special "arm64" tag needed, the platform flag does the selection.
FROM python:3.13-slim

WORKDIR /app

# Dependencies are pre-downloaded on the HOST as arm64 wheels (see README) via:
#   uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 \
#       --target vendor --only-binary=:all: -r requirements.txt
# then just copied in here -- deliberately NOT running `pip install` inside this container.
# Running pip inside an emulated arm64 container (QEMU, since we're building on x86 Windows)
# is fine for prebuilt wheels, but if pip falls back to compiling anything from source, it
# does so under emulation -- 20-50x slower than native, easily hangs for 30+ minutes.
# Resolving on the host avoids emulation entirely for this step.
COPY vendor/ /app/vendor/
ENV PYTHONPATH=/app/vendor

# Tells the bedrock_agentcore SDK's server to bind 0.0.0.0 (all interfaces) instead of
# 127.0.0.1 (localhost-only). Without this, the container starts fine and looks healthy, but
# every request from outside the container silently gets an empty reply -- confirmed by testing
# locally: curl got "Empty reply from server" until this was set.
ENV DOCKER_CONTAINER=1

# Now copy the actual agent code.
COPY my_calc_agent.py .

# BedrockAgentCoreApp (from the bedrock-agentcore SDK) starts an HTTP server on 8080 and
# listens for POST /invocations -- same port you already tested locally with curl against
# starter-toolkit-cli.
EXPOSE 8080

# Run the agent directly with python -- app.run() (last line of my_calc_agent.py) starts the
# server and blocks. No opentelemetry-instrument wrapper, no non-root user setup -- those are
# toolkit conveniences we're deliberately skipping to keep this version easy to read end to end.
CMD ["python", "my_calc_agent.py"]
