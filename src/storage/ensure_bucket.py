"""Make sure the S3 bucket exists, creating it if necessary."""

import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
        logging.info("Bucket '%s' already exists.", bucket_name)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        # Only a missing bucket is created, other errors are raised
        if code in ("404", "NoSuchBucket", "NotFound"):
            s3.create_bucket(Bucket=bucket_name)
            logging.info("Bucket '%s' created.", bucket_name)
        else:
            raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.info,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        steam=sys.stdout,
    )
    ensure_bucket_exists()