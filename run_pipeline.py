
import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "pipeline.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)


logger = logging.getLogger(__name__)


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
    logger.info("Running script: %s", script_path)
    start_time = time.perf_counter()

    try:
        subprocess.run(
            [sys.executable, str(ROOT / script_path)],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError:
        duration = time.perf_counter() - start_time
        logger.error(
            "Script failed: %s | Duration: %.2fs",
            script_path,
            duration,
        )
        raise

    duration = time.perf_counter() - start_time

    logger.info(
        "Script completed: %s | Duration: %.2fs",
        script_path,
        duration,
    )





def create_gold_view():
    logger.info("Creating Gold view...")
    start_time = time.perf_counter()

    try:
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

        duration = time.perf_counter() - start_time

        logger.info(
            "Gold view created successfully | Duration: %.2fs",
            duration,
        )

    except Exception:
        duration = time.perf_counter() - start_time

        logger.exception(
            "Failed to create Gold view | Duration: %.2fs",
            duration,
        )
        raise



def run_data_quality_checks():
    logger.info("Running data quality checks...")
    start_time = time.perf_counter()

    try:
        sql_path = ROOT / "sql" / "data_quality_checks.sql"
        sql = sql_path.read_text(encoding="utf-8")

        with psycopg.connect(
            host="localhost",
            port=5432,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ) as conn:
            with conn.cursor() as cursor:
                for statement in sql.split(";"):
                    if not statement.strip():
                        continue

                    cursor.execute(statement)
                    result = cursor.fetchone()

                    if result is None:
                        continue

                    check_name, failures = result

                    if failures > 0:
                        raise ValueError(
                            f"Data quality check failed: {check_name} "
                            f"({failures} failures)"
                        )

                    logger.info(
                        "Data quality check passed: %s",
                        check_name,
                    )

        duration = time.perf_counter() - start_time
        logger.info(
            "All data quality checks passed | Duration: %.2fs",
            duration,
        )

    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "Data quality checks failed | Duration: %.2fs",
            duration,
        )
        raise


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

    if args.league_id is not None:
        os.environ["LEAGUE_ID"] = str(args.league_id)

    if args.season is not None:
        os.environ["SEASON"] = str(args.season)

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
        
    pipeline_start_time = time.perf_counter()
    logger.info("Starting football data pipeline")
    logger.info(
        "Configuration: league=%s, season=%s",
        os.environ["LEAGUE_ID"],
        os.environ["SEASON"],
    )
    
    run_script("src/storage/ensure_bucket.py")

    if args.fetch:
        logger.info("API fetch enabled")
        run_script("src/ingestion/fetch_api_football.py")
    else:
        logger.info("Skipping API fetch; using data from RustFS")

    run_script("src/processing/transform_fixtures.py")
    run_script("src/warehouse/load_fixtures.py")
    create_gold_view()
    run_data_quality_checks()

    total_duration = time.perf_counter() - pipeline_start_time

    logger.info(
        "Pipeline completed successfully | Total duration: %.2fs",
        total_duration,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
