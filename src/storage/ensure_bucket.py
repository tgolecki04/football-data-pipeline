import os 

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

def ensure_bucket_exists() -> None:
    """Create the S3 bucket from S3_BUCKET if it does not exist yet."""
    bucket_name = os.environ["S3_BUCKET"]

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )

    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already exists.")
    except ClientError as error:
        code = error.response["Error"]["Code"]
        # Only a missing bucket is created, other errors are raised
        if code in ("404", "NoSuchBucket", "NotFound"):
            s3.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created.")
        else:
            raise

if __name__ == "__main__":
    ensure_bucket_exists()