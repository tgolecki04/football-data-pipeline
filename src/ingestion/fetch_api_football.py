
import json
import os
from datetime import datetime, timezone

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://v3.football.api-sports.io/fixtures"

API_KEY = os.environ["API_FOOTBALL_KEY"]
BUCKET = os.environ["S3_BUCKET"]

# Premier League = 39
# Sezon 2023/2024 = 2023
params = {
    "league": 39,
    "season": 2023,
}

headers = {
    "x-apisports-key": API_KEY,
}

print("Pobieram dane z API-FOOTBALL...")

response = requests.get(
    API_URL,
    headers=headers,
    params=params,
    timeout=30,
)

response.raise_for_status()

data = response.json()

# API może zwrócić błąd nawet przy HTTP 200
if data.get("errors"):
    raise RuntimeError(f"Błąd API: {data['errors']}")

matches = data.get("response", [])

print(f"Pobrano meczów: {len(matches)}")
print(
    "Pozostałe requesty dzisiaj:",
    response.headers.get(
        "x-ratelimit-requests-remaining",
        "brak informacji",
    ),
)

# Nie zapisujemy pustych odpowiedzi
if not matches:
    raise RuntimeError("API nie zwróciło meczów.")

# Połączenie z RustFS
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1",
)

timestamp = datetime.now(timezone.utc).strftime(
    "%Y%m%dT%H%M%SZ"
)

object_key = (
    "bronze/api_football/"
    "premier_league/season_2023/"
    f"fixtures_{timestamp}.json"
)

# Zapisujemy pełną odpowiedź API
s3.put_object(
    Bucket=BUCKET,
    Key=object_key,
    Body=json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8"),
    ContentType="application/json",
)

print("Dane zapisane w RustFS!")
print(f"Bucket: {BUCKET}")
print(f"Obiekt: {object_key}")
