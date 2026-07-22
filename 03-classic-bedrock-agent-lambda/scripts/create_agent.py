"""
Creates the classic Bedrock Agent + Lambda action group for the calculator demo.

Run after:
1. IAM policy (BedrockAgentLambdaAccess) is attached to always_learner (see ../iam/)
2. ../lambda/calculator_lambda.py and ../schema/calculator-schema.json exist

Usage:
    python create_agent.py

Safe to rerun: creates roles/Lambda/agent only if they don't already exist, updates
Lambda code if the function already exists.
"""
import json
import time
import zipfile
import io
from pathlib import Path

import boto3

REGION = "us-east-1"
ACCOUNT_ID = "486517829337"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

LAMBDA_FUNCTION_NAME = "CalcAgentCalculatorLambda"
LAMBDA_ROLE_NAME = "CalcAgentLambdaExecutionRole"
AGENT_NAME = "ClassicCalculatorAgent"
AGENT_ROLE_NAME = "BedrockAgentServiceRole-Calculator"
ACTION_GROUP_NAME = "CalculatorActions"

MODULE_ROOT = Path(__file__).resolve().parent.parent
LAMBDA_SOURCE = MODULE_ROOT / "lambda" / "calculator_lambda.py"
SCHEMA_SOURCE = MODULE_ROOT / "schema" / "calculator-schema.json"

iam = boto3.client("iam", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)
bedrock_agent = boto3.client("bedrock-agent", region_name=REGION)

LAMBDA_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}

AGENT_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {"aws:SourceAccount": ACCOUNT_ID},
            "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/*"},
        },
    }],
}


def get_or_create_role(role_name, trust_policy, managed_policy_arns):
    try:
        role = iam.get_role(RoleName=role_name)
        print(f"Role {role_name} already exists.")
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
    )
    for policy_arn in managed_policy_arns:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    print(f"Created role {role_name}, waiting for IAM propagation...")
    time.sleep(10)
    return role["Role"]["Arn"]


def deploy_lambda(role_arn):
    code = LAMBDA_SOURCE.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("calculator_lambda.py", code)
    buf.seek(0)

    try:
        lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        print(f"Lambda {LAMBDA_FUNCTION_NAME} exists, updating code...")
        lambda_client.update_function_code(FunctionName=LAMBDA_FUNCTION_NAME, ZipFile=buf.getvalue())
        response = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        return response["Configuration"]["FunctionArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    response = lambda_client.create_function(
        FunctionName=LAMBDA_FUNCTION_NAME,
        Runtime="python3.12",
        Role=role_arn,
        Handler="calculator_lambda.lambda_handler",
        Code={"ZipFile": buf.getvalue()},
        Timeout=10,
        MemorySize=128,
    )
    print(f"Created Lambda {LAMBDA_FUNCTION_NAME}")
    return response["FunctionArn"]


def allow_bedrock_to_invoke_lambda(agent_arn):
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNCTION_NAME,
            StatementId="AllowBedrockInvoke",
            Action="lambda:InvokeFunction",
            Principal="bedrock.amazonaws.com",
            SourceArn=agent_arn,
        )
        print("Granted Bedrock permission to invoke Lambda.")
    except lambda_client.exceptions.ResourceConflictException:
        print("Lambda resource policy already grants Bedrock access, skipping.")


def find_existing_agent():
    paginator = bedrock_agent.get_paginator("list_agents")
    for page in paginator.paginate():
        for summary in page["agentSummaries"]:
            if summary["agentName"] == AGENT_NAME:
                return summary["agentId"]
    return None


def create_agent(agent_role_arn):
    existing = find_existing_agent()
    if existing:
        print(f"Agent {AGENT_NAME} already exists ({existing}).")
        return existing

    response = bedrock_agent.create_agent(
        agentName=AGENT_NAME,
        agentResourceRoleArn=agent_role_arn,
        foundationModel=MODEL_ID,
        instruction=(
            "You are a helpful assistant that can perform calculations. "
            "Use the calculate function for any math problems."
        ),
        idleSessionTTLInSeconds=600,
    )
    return response["agent"]["agentId"]


def wait_for_agent_status(agent_id, target_statuses, max_wait=120):
    start = time.time()
    while time.time() - start < max_wait:
        resp = bedrock_agent.get_agent(agentId=agent_id)
        status = resp["agent"]["agentStatus"]
        print(f"Agent status: {status}")
        if status in target_statuses:
            return status
        time.sleep(5)
    raise TimeoutError(f"Agent did not reach {target_statuses} within {max_wait}s")


def create_action_group(agent_id, lambda_arn):
    function_schema = json.loads(SCHEMA_SOURCE.read_text())

    existing = bedrock_agent.list_agent_action_groups(agentId=agent_id, agentVersion="DRAFT")
    for group in existing["actionGroupSummaries"]:
        if group["actionGroupName"] == ACTION_GROUP_NAME:
            print(f"Action group {ACTION_GROUP_NAME} already exists, skipping.")
            return

    bedrock_agent.create_agent_action_group(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupName=ACTION_GROUP_NAME,
        actionGroupExecutor={"lambda": lambda_arn},
        functionSchema=function_schema,
        actionGroupState="ENABLED",
    )
    print("Action group created.")


def main():
    lambda_role_arn = get_or_create_role(
        LAMBDA_ROLE_NAME,
        LAMBDA_TRUST_POLICY,
        ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
    )

    agent_role_arn = get_or_create_role(AGENT_ROLE_NAME, AGENT_TRUST_POLICY, [])
    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            "Resource": "*",
        }],
    }
    iam.put_role_policy(
        RoleName=AGENT_ROLE_NAME,
        PolicyName="AllowModelInvocation",
        PolicyDocument=json.dumps(inline_policy),
    )

    lambda_arn = deploy_lambda(lambda_role_arn)

    agent_id = create_agent(agent_role_arn)
    print(f"Agent ID: {agent_id}")
    wait_for_agent_status(agent_id, ["NOT_PREPARED", "PREPARED"])

    create_action_group(agent_id, lambda_arn)

    agent_arn = f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/{agent_id}"
    allow_bedrock_to_invoke_lambda(agent_arn)

    bedrock_agent.prepare_agent(agentId=agent_id)
    wait_for_agent_status(agent_id, ["PREPARED"])

    print("\nDone.")
    print("Agent ID:", agent_id)
    print("Test via the Bedrock console, or run:")
    print(f'  python test_agent.py {agent_id} "What is 25 * 4?"')
    print("(uses the built-in TSTALIASID test alias, no formal alias needed)")


if __name__ == "__main__":
    main()
