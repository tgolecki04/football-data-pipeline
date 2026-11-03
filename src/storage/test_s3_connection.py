"""Check that the connection to RustFS (S3) works correctly."""

import logging
import sys
import os

import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1",
)

bucket_name = os.environ["S3_BUCKET"]

response = s3.list_objects_v2(
    Bucket=bucket_name
)

logging.info("RustFs connection works: bucket=%s, objects=%d", bucket_name, response.get("KeyCount", 0),)
