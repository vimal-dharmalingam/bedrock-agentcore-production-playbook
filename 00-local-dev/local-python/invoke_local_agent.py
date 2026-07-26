"""
Invokes the locally running calculator agent over plain HTTP -- no TLS needed, it's localhost.

Usage:
    python invoke_local_agent.py "What is 25 * 4?"
"""
import json
import sys
import urllib.request

URL = "http://localhost:8080/invoke"


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python invoke_local_agent.py "your prompt"')

    prompt = sys.argv[1]
    data = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(
        URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    print(f"POST {URL}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())

    print("Agent response:", payload)


if __name__ == "__main__":
    main()
