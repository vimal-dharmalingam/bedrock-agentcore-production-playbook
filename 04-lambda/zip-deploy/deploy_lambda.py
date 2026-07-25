"""
Deploys deployment_package.zip as a plain AWS Lambda function -- no AgentCore Runtime
involved at all. Creates an execution role scoped for Lambda (not AgentCore) and either
creates or updates the function, same idempotent pattern as every other deploy script in
this repo.

Run build_lambda_package.py first. Then, from this folder:
    python deploy_lambda.py

Safe to rerun.
"""
import json
import time
from pathlib import Path

import boto3

REGION = "us-east-1"
FUNCTION_NAME = "calc_agent_lambda"
ROLE_NAME = "CalcAgentLambdaExecutionRole"
RUNTIME = "python3.13"
HANDLER = "lambda_function.lambda_handler"
TIMEOUT_SECONDS = 30
MEMORY_MB = 512

FOLDER = Path(__file__).resolve().parent
ZIP_PATH = FOLDER / "deployment_package.zip"

sts = boto3.client("sts", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)

ACCOUNT_ID = sts.get_caller_identity()["Account"]

# Trust policy: lambda.amazonaws.com, not bedrock-agentcore.amazonaws.com -- the whole point
# of this module is that this agent runs on a completely different AWS service now.
TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}

# Much shorter than any AgentCore execution policy -- Lambda's own basic-execution
# permissions (logs) plus the one thing our agent actually needs (calling the model).
EXECUTION_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "LambdaBasicExecution",
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:/aws/lambda/{FUNCTION_NAME}*",
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
        PolicyName="CalcAgentLambdaExecutionPolicy",
        PolicyDocument=json.dumps(EXECUTION_POLICY),
    )
    print(f"Created role {ROLE_NAME}, waiting for IAM propagation...")
    time.sleep(10)
    return role["Role"]["Arn"]


def deploy(role_arn):
    with open(ZIP_PATH, "rb") as f:
        zip_bytes = f.read()

    try:
        lambda_client.get_function(FunctionName=FUNCTION_NAME)
        exists = True
    except lambda_client.exceptions.ResourceNotFoundException:
        exists = False

    if exists:
        print(f"Function {FUNCTION_NAME} exists, updating code...")
        lambda_client.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
        lambda_client.get_waiter("function_updated").wait(FunctionName=FUNCTION_NAME)
        response = lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Timeout=TIMEOUT_SECONDS,
            MemorySize=MEMORY_MB,
        )
        return response["FunctionArn"]

    print(f"Creating function {FUNCTION_NAME}...")
    response = lambda_client.create_function(
        FunctionName=FUNCTION_NAME,
        Runtime=RUNTIME,
        Role=role_arn,
        Handler=HANDLER,
        Code={"ZipFile": zip_bytes},
        Timeout=TIMEOUT_SECONDS,
        MemorySize=MEMORY_MB,
        Architectures=["x86_64"],
    )
    lambda_client.get_waiter("function_active").wait(FunctionName=FUNCTION_NAME)
    return response["FunctionArn"]


def main():
    if not ZIP_PATH.exists():
        raise SystemExit(f"{ZIP_PATH} not found. Run build_lambda_package.py first.")

    role_arn = ensure_execution_role()
    function_arn = deploy(role_arn)

    print("\nDone.")
    print("Function ARN:", function_arn)
    print(f'\nTest it with: python invoke_lambda_agent.py "What is 25 * 4?"')


if __name__ == "__main__":
    main()
