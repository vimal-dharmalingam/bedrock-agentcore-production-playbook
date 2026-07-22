"""
Lists all AgentCore Runtimes in your account/region.

Usage:
    python list_agents.py
    python list_agents.py --region us-west-2
"""
import argparse

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="List AgentCore Runtimes.")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)
    response = client.list_agent_runtimes()

    for runtime in response["agentRuntimes"]:
        print(runtime["agentRuntimeId"], "|", runtime["agentRuntimeName"], "|", runtime["status"])


if __name__ == "__main__":
    main()
