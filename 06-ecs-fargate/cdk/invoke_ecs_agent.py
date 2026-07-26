"""
Invokes the ECS Fargate-hosted calculator agent over HTTP, through the ALB -- same stdlib-only
approach as invoke_ec2_agent.py, just hitting a load balancer DNS name on port 80 instead of an
instance's public IP on port 8080.

Usage:
    python invoke_ecs_agent.py <ALB_DNS_NAME> "What is 25 * 4?"

Get <ALB_DNS_NAME> from the CDK deploy output ("LoadBalancerDNS") or:
    aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'CalcAgent')].DNSName" --output text
"""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python invoke_ecs_agent.py <ALB_DNS_NAME> "your prompt"')

    dns_name = sys.argv[1]
    prompt = sys.argv[2]
    url = f"http://{dns_name}/invoke"

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
