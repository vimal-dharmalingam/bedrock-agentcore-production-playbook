"""
Invokes the CloudFormation-deployed Lambda agent.

Usage:
    python invoke_lambda_agent.py "What is 25 * 4?"
"""
import json
import sys

import boto3

REGION = "us-east-1"
FUNCTION_NAME = "calc_agent_lambda_cfn"


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python invoke_lambda_agent.py "your prompt"')

    prompt = sys.argv[1]

    client = boto3.client("lambda", region_name=REGION)
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"prompt": prompt}).encode(),
    )

    payload = json.loads(response["Payload"].read())

    if response.get("FunctionError"):
        print("Lambda returned an error:")
        print(json.dumps(payload, indent=2))
    else:
        print("Agent response:", payload)


if __name__ == "__main__":
    main()
