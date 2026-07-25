"""
Uploads deployment_package.zip to S3 -- a step CloudFormation itself cannot do.

Same lesson as 01-agentcore-runtime/cloudformation with its container image: CloudFormation can
only *reference* an artifact that already exists somewhere (S3 object, ECR image, AMI, etc.), it
can never build one. For a container it was "docker build && docker push" done outside the
template; for a Lambda zip it's "upload the zip to S3" done outside the template. Same shape,
different artifact type.

Reuses the same bucket 01-agentcore-runtime/direct-code-zip already created
(bedrock-agentcore-code-{account}-{region}) under a new key prefix, rather than creating a
second bucket -- the existing IAM policy's S3 access is scoped to the "bedrock-agentcore-*"
bucket-name pattern, so reusing it means zero new permission gaps.

Run from inside 04-lambda/cloudformation/, after build_lambda_package.py:
    python upload_code.py
"""
from pathlib import Path

import boto3

REGION = "us-east-1"
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

BUCKET_NAME = f"bedrock-agentcore-code-{ACCOUNT_ID}-{REGION}"
S3_KEY = "lambda-cloudformation/deployment_package.zip"

ZIP_PATH = Path(__file__).resolve().parent / "deployment_package.zip"

s3 = boto3.client("s3", region_name=REGION)


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


def upload():
    if not ZIP_PATH.exists():
        raise SystemExit("deployment_package.zip not found -- run build_lambda_package.py first.")

    print(f"Uploading {ZIP_PATH.name} to s3://{BUCKET_NAME}/{S3_KEY} ...")
    s3.upload_file(str(ZIP_PATH), BUCKET_NAME, S3_KEY, ExtraArgs={"ExpectedBucketOwner": ACCOUNT_ID})
    print("Uploaded.")
    print(f"\nCodeS3Bucket = {BUCKET_NAME}")
    print(f"CodeS3Key    = {S3_KEY}")


if __name__ == "__main__":
    ensure_bucket()
    upload()
