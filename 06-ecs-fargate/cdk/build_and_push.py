"""
Builds the container image ONCE and pushes it to its own ECR repo, so cdk_stack.py can point at
a fixed image tag instead of using ContainerImage.from_asset() (which would run `docker build`
again on every single `cdk deploy`). Run this only when container/ actually changes; rerun
`cdk deploy` on its own for everything else (IAM, ALB, service config, etc.).

Usage:
    python build_and_push.py
"""
import subprocess

import boto3

REGION = "us-east-1"
REPO_NAME = "bedrock-agentcore-calc-agent-ecs-fargate"
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
    import base64

    token = ecr.get_authorization_token()["authorizationData"][0]
    registry = token["proxyEndpoint"]
    # authorizationToken is base64("AWS:<password>") -- decode it, then feed just the password
    # to `docker login` the normal way (matches the `aws ecr get-login-password` CLI pattern
    # used in 01-agentcore-runtime/manual-container-build, done here via boto3 instead).
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
