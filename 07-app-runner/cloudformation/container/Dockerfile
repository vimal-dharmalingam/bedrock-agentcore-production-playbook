# linux/amd64, matching App Runner's default architecture -- same reasoning as
# 06-ecs-fargate/cdk/container/Dockerfile. Native build on this Windows host, no QEMU.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
