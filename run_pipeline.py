
import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def positive_int(value):
    """Validate that the value is a positive integer."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Value must be an integer."
        ) from exc

    if number <= 0:
        raise argparse.ArgumentTypeError(
            "Value must be greater than zero."
        )

    return number


def run_script(script_path):
    print(f"\nRunning: {script_path}", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / script_path)],
        cwd=ROOT,
        check=True,
    )


def create_gold_view():
    print("\nCreating Gold view...", flush=True)

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

    print("View gold_team_stats is ready!")


def main():
    parser = argparse.ArgumentParser(
        description="Football Data Pipeline"
    )

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch new data from API-FOOTBALL",
    )
    parser.add_argument(
        "--league-id",
        type=positive_int,
        help="League ID; defaults to the value in .env",
    )
    parser.add_argument(
        "--season",
        type=positive_int,
        help="Season; defaults to the value in .env",
    )

    args = parser.parse_args()

    # CLI arguments take precedence over .env values.
    if args.league_id is not None:
        os.environ["LEAGUE_ID"] = str(args.league_id)

    if args.season is not None:
        os.environ["SEASON"] = str(args.season)

    # Validate the configuration before running the pipeline.
    for variable in ("LEAGUE_ID", "SEASON"):
        if variable not in os.environ:
            parser.error(
                f"Missing {variable}. Set it in .env "
                "or provide the corresponding CLI argument."
            )

        try:
            value = positive_int(os.environ[variable])
        except argparse.ArgumentTypeError as exc:
            parser.error(f"Invalid {variable}: {exc}")

        os.environ[variable] = str(value)

    print(
        f"Configuration: league={os.environ['LEAGUE_ID']}, "
        f"season={os.environ['SEASON']}"
    )

    if args.fetch:
        run_script("src/ingestion/fetch_api_football.py")
    else:
        print("\nSkipping API fetch; using data from RustFS.")

    run_script("src/processing/transform_fixtures.py")
    run_script("src/warehouse/load_fixtures.py")
    create_gold_view()

    print("\nPIPELINE COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
