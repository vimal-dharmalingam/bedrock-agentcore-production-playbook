"""
CDK stack for a plain Lambda-hosted version of the calculator agent.

Compare to 01-agentcore-runtime/cdk/cdk_stack.py: that one needed AgentRuntimeArtifact,
platform=Platform.LINUX_ARM64, and a Runtime construct that only recently graduated into
aws-cdk-lib. Lambda's `Function` L2 construct has existed for years and is about as mature
as CDK constructs get -- no arm64 requirement, no container-vs-code-zip artifact type to
choose, just point `code` at a folder and go.

Same one gap as the AgentCore CDK module, though: the L2 construct auto-creates an execution
role with basic Lambda logging permissions, but NOT bedrock:InvokeModel -- that's still on us.
"""
from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from constructs import Construct

BUILD_DIR = str(Path(__file__).resolve().parent / "build")


class CalcAgentLambdaCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        function = _lambda.Function(
            self,
            "CalcAgentLambdaFunction",
            function_name="calc_agent_lambda_cdk",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset(BUILD_DIR),
            timeout=Duration.seconds(30),
            memory_size=512,
        )

        # Not auto-granted by the construct -- same lesson as the AgentCore CDK module.
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:*",
                ],
            )
        )

        self.function = function
