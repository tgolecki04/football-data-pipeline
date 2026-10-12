
import os

import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("RUSTFS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("RUSTFS_SECRET_KEY"),
    region_name="us-east-1",
)

bucket_name = os.getenv("S3_BUCKET")

response = s3.list_objects_v2(
    Bucket=bucket_name
)

print("Połączenie z RustFS działa!")
print("Bucket:", bucket_name)
print("Liczba obiektów:", response.get("KeyCount", 0))
