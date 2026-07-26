# Deliberately linux/amd64, matching Fargate's default CPU architecture -- unlike
# 01-agentcore-runtime (which AgentCore Runtime forces to arm64), there's no cross-platform
# build here. Building amd64 on an x86 Windows host is a NATIVE build, not QEMU emulation, so
# a plain `pip install` at build time is fine -- none of the vendor/ wheel-prefetch dance
# needed everywhere in 01-agentcore-runtime and 04-lambda applies here.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
