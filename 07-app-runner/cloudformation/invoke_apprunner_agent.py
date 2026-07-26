"""
Invokes the App Runner-hosted calculator agent over HTTPS -- App Runner gives every service a
public HTTPS endpoint by default, unlike the plain HTTP ALB DNS name in 06-ecs-fargate.

Usage:
    python invoke_apprunner_agent.py <SERVICE_URL> "What is 25 * 4?"

Get <SERVICE_URL> from the CloudFormation stack's ServiceUrl output, or:
    aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='calc-agent-app-runner'].ServiceUrl" --output text
"""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python invoke_apprunner_agent.py <SERVICE_URL> "your prompt"')

    service_url = sys.argv[1].rstrip("/")
    prompt = sys.argv[2]
    url = f"https://{service_url}/invoke"

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
