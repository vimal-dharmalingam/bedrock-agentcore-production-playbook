# Same validated pattern from manual-container-build/Dockerfile and cdk/agent/Dockerfile.
# Kept identical on purpose -- the point of this module is CloudFormation's orchestration
# layer, not re-solving problems already solved (QEMU compile hang, DOCKER_CONTAINER binding).

FROM python:3.13-slim

WORKDIR /app

# Dependencies pre-downloaded on the HOST as arm64 wheels, before `docker build`:
#   uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 \
#       --target vendor --only-binary=:all: -r requirements.txt
COPY vendor/ /app/vendor/
ENV PYTHONPATH=/app/vendor

# Required so the bedrock_agentcore SDK's server binds 0.0.0.0 instead of 127.0.0.1.
ENV DOCKER_CONTAINER=1

COPY my_calc_agent.py .

EXPOSE 8080

CMD ["python", "my_calc_agent.py"]
