# Deliberately linux/amd64, matching the managed node group's default instance architecture
# (t3.small is x86_64) -- same reasoning as 06-ecs-fargate: building amd64 on an x86 Windows
# host is a NATIVE build, not QEMU emulation, so a plain `pip install` at build time is fine.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
