"""
Deploys the pushed ECR image to AgentCore Runtime -- the container-based counterpart to
direct-code-zip's deploy_code_zip.py. Same overall shape (ensure execution role, call
create_agent_runtime), but two things differ because we're pointing at a container image
instead of an S3 code zip:

1. The execution role needs ECR pull permissions added (AgentCore has to pull the image at
   startup) -- direct-code-zip's role didn't need any of this since there was no image.
2. agentRuntimeArtifact uses "containerConfiguration" (just a containerUri) instead of
   "codeConfiguration" (S3 location + runtime + entryPoint).

Run this AFTER: docker build, docker push (see README for the exact commands already run).
    python deploy_container.py

Safe to rerun -- reuses the execution role if it exists, calls update_agent_runtime if the
agent runtime already exists.
"""
import json
import time

import boto3

REGION = "us-east-1"
AGENT_NAME = "calc_agent_manual_container"
ROLE_NAME = "BedrockAgentCoreManualContainerExecutionRole"
ECR_REPO_NAME = "bedrock-agentcore-calc-agent-manual"

sts = boto3.client("sts", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
agentcore = boto3.client("bedrock-agentcore-control", region_name=REGION)

ACCOUNT_ID = sts.get_caller_identity()["Account"]
CONTAINER_URI = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:latest"

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {"aws:SourceAccount": ACCOUNT_ID},
            "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT_ID}:*"},
        },
    }],
}

# Same baseline as direct-code-zip's execution policy (logs, xray, cloudwatch, bedrock invoke),
# PLUS the ECR pull permissions a container-based runtime needs that a code-zip runtime doesn't.
EXECUTION_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
            "Resource": [f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*"],
        },
        {
            "Effect": "Allow",
            "Action": ["logs:DescribeLogGroups"],
            "Resource": [f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:*"],
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": [f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"],
        },
        {
            "Effect": "Allow",
            "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"],
            "Resource": ["*"],
        },
        {
            "Effect": "Allow",
            "Resource": "*",
            "Action": "cloudwatch:PutMetricData",
            "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
        },
        {
            "Sid": "BedrockModelInvocation",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:*",
            ],
        },
        {
            "Sid": "ECRImagePull",
            "Effect": "Allow",
            "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
            "Resource": [f"arn:aws:ecr:{REGION}:{ACCOUNT_ID}:repository/{ECR_REPO_NAME}"],
        },
        {
            # GetAuthorizationToken is account-wide by design -- ECR doesn't support scoping
            # it to a single repository, unlike the pull actions above.
            "Sid": "ECRAuth",
            "Effect": "Allow",
            "Action": ["ecr:GetAuthorizationToken"],
            "Resource": "*",
        },
    ],
}


def ensure_execution_role():
    try:
        role = iam.get_role(RoleName=ROLE_NAME)
        print(f"Role {ROLE_NAME} already exists.")
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    role = iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
    )
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="ManualContainerExecutionPolicy",
        PolicyDocument=json.dumps(EXECUTION_POLICY),
    )
    print(f"Created role {ROLE_NAME}, waiting for IAM propagation...")
    time.sleep(10)
    return role["Role"]["Arn"]


def find_existing_agent_runtime():
    paginator = agentcore.get_paginator("list_agent_runtimes")
    for page in paginator.paginate():
        for runtime in page["agentRuntimes"]:
            if runtime["agentRuntimeName"] == AGENT_NAME:
                return runtime["agentRuntimeId"]
    return None


def deploy(role_arn):
    artifact = {
        "containerConfiguration": {
            "containerUri": CONTAINER_URI,
        }
    }

    existing_id = find_existing_agent_runtime()
    if existing_id:
        print(f"Agent runtime {AGENT_NAME} exists ({existing_id}), updating...")
        response = agentcore.update_agent_runtime(
            agentRuntimeId=existing_id,
            agentRuntimeArtifact=artifact,
            networkConfiguration={"networkMode": "PUBLIC"},
            roleArn=role_arn,
        )
        return existing_id, response["agentRuntimeArn"]

    print(f"Creating agent runtime {AGENT_NAME}...")
    response = agentcore.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        agentRuntimeArtifact=artifact,
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
        lifecycleConfiguration={"idleRuntimeSessionTimeout": 300, "maxLifetime": 1800},
    )
    return response["agentRuntimeId"], response["agentRuntimeArn"]


def main():
    print(f"Deploying container image: {CONTAINER_URI}")
    role_arn = ensure_execution_role()
    agent_id, agent_arn = deploy(role_arn)

    print("\nDone.")
    print("Agent Runtime ID:", agent_id)
    print("Agent Runtime ARN:", agent_arn)
    print(f'\nTest it with: python invoke_container_agent.py {agent_id} "What is 25 * 4?"')


if __name__ == "__main__":
    main()
