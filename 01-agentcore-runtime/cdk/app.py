"""
CDK app entry point. `cdk deploy` / `cdk synth` run this file (see cdk.json).
All it does: create the App, instantiate our stack inside it, synth.
The actual resource definitions live in cdk_stack.py -- this file stays thin on purpose.
"""
import aws_cdk as cdk

from cdk_stack import CalcAgentCdkStack

app = cdk.App()

CalcAgentCdkStack(
    app,
    "CalcAgentCdkStack",
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
