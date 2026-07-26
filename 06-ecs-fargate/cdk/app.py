import aws_cdk as cdk

from cdk_stack import CalcAgentEcsFargateStack

app = cdk.App()
CalcAgentEcsFargateStack(
    app, "CalcAgentEcsFargateStack",
    env=cdk.Environment(region="us-east-1"),
)
app.synth()
