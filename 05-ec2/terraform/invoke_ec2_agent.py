"""
Invokes the EC2-hosted calculator agent over plain HTTP -- no boto3 client involved, since this
agent has no managed invoke API in front of it (unlike AgentCore Runtime or Lambda). Uses only
the standard library so nothing extra needs installing on your laptop.

Usage:
    python invoke_ec2_agent.py <PUBLIC_IP> "What is 25 * 4?"

Get <PUBLIC_IP> from `terraform output public_ip` after apply.
"""
import json
import sys
import urllib.request

APP_PORT = 8080


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python invoke_ec2_agent.py <PUBLIC_IP> "your prompt"')

    public_ip = sys.argv[1]
    prompt = sys.argv[2]
    url = f"http://{public_ip}:{APP_PORT}/invoke"

    data = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    print(f"POST {url}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())

    print("Agent response:", payload)


if __name__ == "__main__":
    main()
