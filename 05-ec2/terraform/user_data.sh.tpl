#!/bin/bash
# Rendered by Terraform's templatefile(). The app code, requirements, port, and region
# variables are all substituted with real values BEFORE this script ever reaches the
# instance -- by the time bash runs this, there are no Terraform placeholders left, only
# literal text. (Do not write those variable references using dollar-brace syntax directly
# in a comment here -- templatefile() substitutes it wherever it appears in this file,
# comment or not, which is exactly what broke this script the first time around: it spliced
# multi-line file content into the middle of this comment line.)
set -euo pipefail
# tee (not a plain redirect) so output lands in BOTH the log file AND the console -- the EC2
# console's "Get system log" is the only debugging tool available here (no SSH/SSM access by
# design), so it needs to actually see this script's output to be useful.
exec > >(tee /var/log/user-data.log) 2>&1
# Trace every command as it runs -- with output now visible via the console log, this pinpoints
# exactly which command fails instead of just showing the aftermath.
set -x

# The unversioned "python3" package on this AL2023 AMI is 3.9 -- confirmed via a real boot log,
# not assumed -- and strands-agents requires Python >=3.10, so pip fails with "No matching
# distribution found" against the 3.9 venv. python3.11 is available as its own package in the
# base AL2023 repo; installing it explicitly instead of the unversioned default.
dnf install -y python3.11 python3.11-pip

mkdir -p /opt/calc-agent

cat > /opt/calc-agent/app.py << 'PYEOF'
${app_py_content}
PYEOF

cat > /opt/calc-agent/requirements.txt << 'REQEOF'
${requirements_content}
REQEOF

python3.11 -m venv /opt/calc-agent/venv
/opt/calc-agent/venv/bin/pip install --upgrade pip
/opt/calc-agent/venv/bin/pip install -r /opt/calc-agent/requirements.txt

cat > /etc/systemd/system/calc-agent.service << 'SVCEOF'
[Unit]
Description=Calculator Agent (FastAPI + Strands, on EC2)
After=network.target

[Service]
ExecStart=/opt/calc-agent/venv/bin/uvicorn app:app --host 0.0.0.0 --port ${app_port}
WorkingDirectory=/opt/calc-agent
Restart=always
Environment=AWS_DEFAULT_REGION=${aws_region}

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable --now calc-agent
