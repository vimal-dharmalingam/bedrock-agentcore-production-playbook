"""
Builds the container image and pushes it to its own ECR repo -- App Runner (like the ECS
Fargate module) pulls from a fixed, already-pushed image rather than building anything itself.
CloudFormation especially can't build images at all, same lesson as every other CloudFormation
module in this repo.

Usage:
    python build_and_push.py
"""
import base64
import subprocess

import boto3

REGION = "us-east-1"
REPO_NAME = "bedrock-agentcore-calc-agent-app-runner"
IMAGE_TAG = "latest"

ecr = boto3.client("ecr", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)
ACCOUNT_ID = sts.get_caller_identity()["Account"]
IMAGE_URI = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{REPO_NAME}:{IMAGE_TAG}"


def ensure_repo():
    try:
        ecr.describe_repositories(repositoryNames=[REPO_NAME])
        print(f"ECR repo {REPO_NAME} already exists.")
    except ecr.exceptions.RepositoryNotFoundException:
        print(f"Creating ECR repo {REPO_NAME}...")
        ecr.create_repository(repositoryName=REPO_NAME)


def docker_login():
    token = ecr.get_authorization_token()["authorizationData"][0]
    registry = token["proxyEndpoint"]
    user, pw = base64.b64decode(token["authorizationToken"]).decode().split(":", 1)
    subprocess.run(
        ["docker", "login", "--username", user, "--password-stdin", registry],
        input=pw.encode(),
        check=True,
    )


def build_and_push():
    print("Building image (linux/amd64)...")
    subprocess.run(
        ["docker", "build", "--platform", "linux/amd64", "-t", IMAGE_URI, "./container"],
        check=True,
    )
    print(f"Pushing {IMAGE_URI}...")
    subprocess.run(["docker", "push", IMAGE_URI], check=True)
    print(f"\nDone. Image URI:\n{IMAGE_URI}")


if __name__ == "__main__":
    ensure_repo()
    docker_login()
    build_and_push()
