
import io
import os

import boto3
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.environ["S3_BUCKET"]

LEAGUE_ID = int(os.environ["LEAGUE_ID"])
SEASON = int(os.environ["SEASON"])

SILVER_KEY = (
    f"silver/api_football/league_{LEAGUE_ID}/"
    f"season_{SEASON}/"
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

print("Pobieram Parquet z RustFS...")

response = s3.get_object(
    Bucket=BUCKET,
    Key=SILVER_KEY,
)

# 2. Odczyt danych do Pandas
parquet_bytes = response["Body"].read()

df = pd.read_parquet(
    io.BytesIO(parquet_bytes)
)

print(f"Odczytano {len(df)} meczów.")

# 3. Połączenie z PostgreSQL
connection = psycopg.connect(
    host="localhost",
    port=5432,
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)

# 4. Utworzenie tabeli i załadowanie danych
with connection, connection.cursor() as cursor:
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS fixtures (
                fixture_id BIGINT PRIMARY KEY,
                date TIMESTAMPTZ,
                league_id INTEGER,
                season INTEGER,
                round TEXT,
                home_team_id INTEGER,
                home_team TEXT,
                away_team_id INTEGER,
                away_team TEXT,
                home_goals INTEGER,
                away_goals INTEGER,
                status TEXT
            );
        """)

    insert_sql = """
            INSERT INTO fixtures (
                fixture_id,
                date,
                league_id,
                season,
                round,
                home_team_id,
                home_team,
                away_team_id,
                away_team,
                home_goals,
                away_goals,
                status
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (fixture_id)
            DO UPDATE SET
                date = EXCLUDED.date,
                league_id = EXCLUDED.league_id,
                season = EXCLUDED.season,
                round = EXCLUDED.round,
                home_team_id = EXCLUDED.home_team_id,
                home_team = EXCLUDED.home_team,
                away_team_id = EXCLUDED.away_team_id,
                away_team = EXCLUDED.away_team,
                home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals,
                status = EXCLUDED.status;
        """

    # Zamiana wartości Pandas na typy Pythona
    records = []

    for row in df.itertuples(index=False):
        records.append((
            int(row.fixture_id),
            row.date.to_pydatetime(),
            int(row.league_id),
            int(row.season),
            row.round,
            int(row.home_team_id),
            row.home_team,
            int(row.away_team_id),
            row.away_team,
            None if pd.isna(row.home_goals) else int(row.home_goals),
            None if pd.isna(row.away_goals) else int(row.away_goals),
            row.status,
        ))

    cursor.executemany(
        insert_sql,
        records,
    )

    cursor.execute(
        "SELECT COUNT(*) FROM fixtures;"
    )

    total = cursor.fetchone()[0]

print("Dane załadowane do PostgreSQL!")
print(f"Liczba meczów w tabeli: {total}")

connection.close()
