
import io
import json
import os

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.environ["S3_BUCKET"]

BRONZE_PREFIX = (
    "bronze/api_football/"
    "premier_league/season_2023/"
)

SILVER_KEY = (
    "silver/api_football/"
    "premier_league/season_2023/"
    "fixtures.parquet"
)

# 1. Połączenie z RustFS
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1",
)

# 2. Znalezienie plików Bronze
objects = []

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=BUCKET,
    Prefix=BRONZE_PREFIX,
):
    objects.extend(
        obj for obj in page.get("Contents", [])
        if obj["Key"].endswith(".json")
    )

if not objects:
    raise RuntimeError("Nie znaleziono danych Bronze.")

latest = max(objects, key=lambda obj: obj["LastModified"])
bronze_key = latest["Key"]

print("Odczytuję:", bronze_key)

# 3. Pobranie JSON z RustFS
response = s3.get_object(
    Bucket=BUCKET,
    Key=bronze_key,
)

data = json.loads(
    response["Body"].read().decode("utf-8")
)

matches = data["response"]

# 4. Zamiana JSON na wiersze tabeli
rows = []

for match in matches:
    fixture = match["fixture"]
    league = match["league"]
    teams = match["teams"]
    goals = match["goals"]

    rows.append({
        "fixture_id": fixture["id"],
        "date": fixture["date"],
        "league_id": league["id"],
        "season": league["season"],
        "round": league.get("round"),
        "home_team_id": teams["home"]["id"],
        "home_team": teams["home"]["name"],
        "away_team_id": teams["away"]["id"],
        "away_team": teams["away"]["name"],
        "home_goals": goals["home"],
        "away_goals": goals["away"],
        "status": fixture["status"]["short"],
    })

df = pd.DataFrame(rows)

if df.empty:
    raise RuntimeError("Brak meczów do przetworzenia.")

# 5. Ustawienie typów danych
df["date"] = pd.to_datetime(
    df["date"],
    utc=True,
)

df = df.drop_duplicates(
    subset=["fixture_id"]
)

df = df.sort_values("date")

# 6. Zapis do Parquet w pamięci
buffer = io.BytesIO()

df.to_parquet(
    buffer,
    engine="pyarrow",
    index=False,
)

# 7. Wysłanie do RustFS
s3.put_object(
    Bucket=BUCKET,
    Key=SILVER_KEY,
    Body=buffer.getvalue(),
    ContentType="application/octet-stream",
)

print("Transformacja zakończona!")
print("Liczba meczów:", len(df))
print("Liczba kolumn:", len(df.columns))
print("Zapisano:", SILVER_KEY)

print("\nPrzykładowe dane:")
print(
    df[
        [
            "date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "status",
        ]
    ].head()
)
