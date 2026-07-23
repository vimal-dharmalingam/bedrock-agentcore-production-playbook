"""
The actual infrastructure definition -- one AgentCore Runtime, built directly from
agent/Dockerfile.

Compare this to manual-container-build/deploy_container.py: there we wrote ~70 lines of
raw IAM policy JSON by hand for the execution role. Here, the Runtime L2 construct's
addExecutionRolePermissions() (see aws-cdk-lib/aws-bedrockagentcore) does most of that
automatically -- logs, X-Ray, CloudWatch metrics, workload-identity tokens, ECR pull for
its own asset repo -- based on AWS's own reference permissions for this resource type.

One thing it does NOT auto-grant: bedrock:InvokeModel. Confirmed by reading the actual
synthesized template (`cdk synth`) -- without adding this ourselves below, the runtime
would deploy successfully and then fail on every real invocation, same failure mode as the
very first error hit in this whole project (ResourceNotFoundException / AccessDenied on
first model call).
"""
from pathlib import Path

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from aws_cdk.aws_bedrockagentcore import AgentRuntimeArtifact, Runtime
from aws_cdk.aws_ecr_assets import Platform
from constructs import Construct

# Directory containing the Dockerfile CDK will build -- resolved relative to this file so
# `cdk deploy` works regardless of what directory you run it from.
AGENT_DIR = str(Path(__file__).resolve().parent / "agent")


class CalcAgentCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # fromAsset builds agent/Dockerfile and pushes the result to a CDK-managed ECR
        # asset repository as part of `cdk deploy`. platform=LINUX_ARM64 is the CDK
        # equivalent of the --platform linux/arm64 flag we passed to `docker build` by
        # hand in manual-container-build -- still mandatory, AgentCore Runtime only runs
        # on arm64 regardless of how the image gets built.
        artifact = AgentRuntimeArtifact.from_asset(
            AGENT_DIR,
            platform=Platform.LINUX_ARM64,
        )

        self.runtime = Runtime(
            self,
            "CalcAgentRuntime",
            runtime_name="calc_agent_cdk",
            agent_runtime_artifact=artifact,
        )

        # Not auto-granted by the construct -- see module docstring above.
        self.runtime.role.add_to_principal_policy(
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:*",
                ],
            )
        )

        # So `cdk deploy` prints the runtime ID directly instead of us having to go find it
        # with list_agents.py every time.
        CfnOutput(self, "AgentRuntimeId", value=self.runtime.agent_runtime_id)
        CfnOutput(self, "AgentRuntimeArn", value=self.runtime.agent_runtime_arn)
