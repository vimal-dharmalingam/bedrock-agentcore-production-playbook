"""
Invokes the EKS-hosted calculator agent over HTTP, through the classic ELB the Service created --
same stdlib-only approach as invoke_ecs_agent.py, just a different DNS name source.

Usage:
    python invoke_eks_agent.py <ELB_DNS_NAME> "What is 25 * 4?"

Get <ELB_DNS_NAME> with:
    kubectl get service calc-agent-service -o jsonpath="{.status.loadBalancer.ingress[0].hostname}"
"""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python invoke_eks_agent.py <ELB_DNS_NAME> "your prompt"')

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
