"""
Deploys deployment_package.zip to AgentCore Runtime using direct code deployment --
no Docker, no ECR, no CodeBuild. Just: upload the zip to S3, create an execution role,
call create_agent_runtime pointing at the zip.

Run build_deployment_package.py first. Then, from this folder:
    python deploy_code_zip.py

Safe to rerun: creates the S3 bucket / IAM role / agent runtime only if they don't already
exist; re-uploads the zip and calls update_agent_runtime if the agent already exists.
"""
import json
import time
from pathlib import Path

import boto3

REGION = "us-east-1"
AGENT_NAME = "calc_agent_direct_zip"
ROLE_NAME = "BedrockAgentCoreDirectZipExecutionRole"
PYTHON_RUNTIME = "PYTHON_3_13"

FOLDER = Path(__file__).resolve().parent
ZIP_PATH = FOLDER / "deployment_package.zip"

sts = boto3.client("sts", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
agentcore = boto3.client("bedrock-agentcore-control", region_name=REGION)

ACCOUNT_ID = sts.get_caller_identity()["Account"]
BUCKET_NAME = f"bedrock-agentcore-code-{ACCOUNT_ID}-{REGION}"
S3_PREFIX = f"{AGENT_NAME}/deployment_package.zip"

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

# "Direct deploy" execution role -- no ECR permissions needed, unlike the container-based
# execution role, since there's no image to pull.
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
    ],
}


def ensure_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"S3 bucket {BUCKET_NAME} already exists.")
    except s3.exceptions.ClientError:
        print(f"Creating S3 bucket {BUCKET_NAME}...")
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(Bucket=BUCKET_NAME, CreateBucketConfiguration={"LocationConstraint": REGION})


def upload_zip():
    print(f"Uploading {ZIP_PATH.name} to s3://{BUCKET_NAME}/{S3_PREFIX} ...")
    s3.upload_file(str(ZIP_PATH), BUCKET_NAME, S3_PREFIX, ExtraArgs={"ExpectedBucketOwner": ACCOUNT_ID})


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
        PolicyName="DirectZipExecutionPolicy",
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
        "codeConfiguration": {
            "code": {"s3": {"bucket": BUCKET_NAME, "prefix": S3_PREFIX}},
            "runtime": PYTHON_RUNTIME,
            "entryPoint": ["my_calc_agent.py"],
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
    if not ZIP_PATH.exists():
        raise SystemExit(f"{ZIP_PATH} not found. Run build_deployment_package.py first.")

    ensure_bucket()
    upload_zip()
    role_arn = ensure_execution_role()
    agent_id, agent_arn = deploy(role_arn)

    print("\nDone.")
    print("Agent Runtime ID:", agent_id)
    print("Agent Runtime ARN:", agent_arn)
    print(f'\nTest it with: python invoke_code_zip_agent.py {agent_id} "What is 25 * 4?"')


if __name__ == "__main__":
    main()
