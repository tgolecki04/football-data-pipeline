
import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def run_script(script_path):
    print(f"\nUruchamiam: {script_path}", flush=True)

    subprocess.run(
        [sys.executable, str(ROOT / script_path)],
        cwd=ROOT,
        check=True,
    )


def create_gold_view():
    print("\nTworzę widok Gold...", flush=True)

    sql_path = ROOT / "sql" / "gold_team_stats.sql"
    sql = sql_path.read_text(encoding="utf-8")

    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)

    print("Widok gold_team_stats jest gotowy!")


def main():
    parser = argparse.ArgumentParser(
        description="Football Data Pipeline"
    )

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Pobierz nowe dane z API-FOOTBALL",
    )

    args = parser.parse_args()

    if args.fetch:
        run_script("src/ingestion/fetch_api_football.py")
    else:
        print("Pomijam API — używam danych z RustFS.")

    run_script("src/processing/transform_fixtures.py")
    run_script("src/warehouse/load_fixtures.py")

    create_gold_view()

    print("\nPIPELINE ZAKOŃCZONY SUKCESEM!")


if __name__ == "__main__":
    main()
