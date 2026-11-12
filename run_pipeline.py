import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


import psycopg
from dotenv import load_dotenv

from src.processing.data_quality_report import generate_data_quality_report
from src.processing.pipeline_report import generate_pipeline_report

FOOTBALL_DATA_COMPETITION_IDS = {
    "PD": 2014,
    "PL": 2021,
    "BL1": 2002,
    "SA": 2019,
    "FL1": 2015,
}

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
        [sys.executable, "-m", script_path.replace("/", ".").removesuffix(".py")],
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



def run_pipeline_stage(stage_name, function, stages):
    logger.info("Starting pipeline stage: %s", stage_name)
    start_time = time.perf_counter()

    try:
        result = function()
        stages[stage_name] = "SUCCESS"
        return result

    except Exception:
        stages[stage_name] = "FAILED"
        logger.exception("Pipeline stage failed: %s", stage_name)
        raise

    finally:
        duration = time.perf_counter() - start_time
        logger.info(
            "Pipeline stage finished: %s | Duration: %.2fs",
            stage_name,
            duration,
        )

GOLD_VIEW_FILES = ("gold_team_stats.sql","gold_team_recent_form.sql")

def create_gold_view():
    logger.info("Creating Gold view...")
    start_time = time.perf_counter()

    try:
        with psycopg.connect(
            host="localhost",
            port=5432,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ) as conn, conn.cursor() as cursor:
            for file_name in GOLD_VIEW_FILES:
                sql_path = (ROOT / "sql" / file_name).read_text(encoding="utf-8")
                cursor.execute(sql_path)

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

        checks = []

        with psycopg.connect(
            host="localhost",
            port=5432,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ) as conn, conn.cursor() as cursor:

            for statement in sql.split(";"):
                if not statement.strip():
                    continue

                cursor.execute(statement)
                result = cursor.fetchone()

                if result is None:
                    continue

                check_name, failures = result

                status = "FAIL" if failures > 0 else "PASS"

                checks.append({
                    "name": check_name,
                    "status": status,
                    "failures": failures,
                })

                if status == "PASS":
                    logger.info(
                        "Data quality check passed: %s",
                        check_name,
                    )
                else:
                    logger.error(
                        "Data quality check failed: %s | Failures: %s",
                        check_name,
                        failures,
                    )

        report = generate_data_quality_report(checks)

        logger.info(
            "Data quality report saved | Status: %s | Failed checks: %s/%s",
            report["overall_status"],
            report["failed_checks"],
            report["total_checks"],
        )

        duration = time.perf_counter() - start_time

        if report["failed_checks"] > 0:
            failed_names = [
                check["name"]
                for check in checks
                if check["status"] == "FAIL"
            ]

            raise ValueError(
                f"Data quality checks failed: "
                f"{', '.join(failed_names)}"
            )

        logger.info(
            "All data quality checks passed | Duration: %.2fs",
            duration,
        )

        return report

    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "Data quality checks failed | Duration: %.2fs",
            duration,
        )
        raise


def run_for_season(fetch: bool, source: str = "api_football") -> None:
    """Run all pipeline stages for the league and season specified in the environment variables."""
    if source not in ("api_football", "football_data"):
        raise ValueError(f"Unsupported provider: {source}")
    if source == "football_data":
        ingestion_script = "src/ingestion/fetch_football_data.py"
        transformation_script = "src/processing/transform_football_data.py"
        loading_script = "src/warehouse/load_football_data.py"
    else:
        ingestion_script = "src/ingestion/fetch_api_football.py"
        transformation_script = "src/processing/transform_fixtures.py"
        loading_script = "src/warehouse/load_fixtures.py"

    started_at = datetime.now(timezone.utc)
    pipeline_start_at = time.perf_counter()
    stages = {
        "bucket": "NOT_RUN",
        "ingestion": "SKIPPED",
        "transformation": "NOT_RUN",
        "loading": "NOT_RUN",
        "gold": "NOT_RUN",
        "data_quality": "NOT_RUN",
    }

    status = "SUCCESS"

    logger.info(
        "Starting pipeline for league_id=%s, season=%s",
        os.environ["LEAGUE_ID"],
        os.environ["SEASON"],
    )

    try:
        run_pipeline_stage(
            "bucket",
            lambda: run_script("src/storage/ensure_bucket.py"),
            stages,
        )

        if fetch:
            run_pipeline_stage(
                "ingestion",
                lambda: run_script(ingestion_script),
                stages,
            )

        run_pipeline_stage(
            "transformation",
            lambda: run_script(transformation_script),
            stages,
        )

        run_pipeline_stage(
            "loading",
            lambda: run_script(loading_script),
            stages,
        )
        run_pipeline_stage("gold", create_gold_view, stages)

        run_pipeline_stage("data_quality", run_data_quality_checks, stages)

    except Exception:
        status = "FAILED"
        raise

    finally:
        finished_at = datetime.now(timezone.utc)
        total_duration = time.perf_counter() - pipeline_start_at

        try:
            report = generate_pipeline_report(
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                league_id=(
                    FOOTBALL_DATA_COMPETITION_IDS[
                        os.environ["COMPETITION_CODE"]
                    ]
                    if source == "football_data"
                    else int(os.environ["LEAGUE_ID"])
                ),
                season=int(os.environ["SEASON"]),
                stages=stages,
            )

            logger.info(
                "Pipeline finished | Status: %s | Duration: %.2fs",
                report["status"],
                total_duration,
            )
        
        except Exception:
            logger.exception("Failed to generate pipeline report")

        logger.info(
            "Pipeline %s | Total Duration: %.2fs",
            status,
            total_duration,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Football Data Pipeline"
    )
    parser.add_argument(
    "--source",
    choices=["api_football", "football_data"],
    default="api_football",
    help="Select the data provider (default: api_football)",
)

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch new data from API-FOOTBALL",
    )
    parser.add_argument(
    "--ingest-only",
    action="store_true",
    help="Run only ingestion into Bronze, without Silver or PostgreSQL",
    )
    parser.add_argument(
        "--transform-only",
        action="store_true",
        help="Run only the Bronze-to-Silver transformation.",
    )
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="Load existing Silver data into PostgreSQL.",
    )
    parser.add_argument(
        "--league-id",
        type=positive_int,
        help="League ID; defaults to the value in .env",
    )
    parser.add_argument(
    "--competition",
    type=str,
    help="Competition code for football-data.org (e.g. PD)",
    )
    parser.add_argument(
        "--season",
        type=positive_int,
        nargs="+",
        help="One or more seasons; defaults to the value in .env",
    )

    args = parser.parse_args()
    if args.load_only and (args.fetch or args.ingest_only or args.transform_only):
        parser.error(
            "--load-only cannot be combined with --fetch, "
            "--ingest-only or --transform-only."
        )
    if args.transform_only and args.ingest_only:
        parser.error(
            "--transform-only and --ingest-only cannot be used together."
        )

    if args.transform_only and args.fetch:
        parser.error(
            "--transform-only cannot be combined with --fetch."
        )
        
    if args.source == "football_data":
        if args.league_id is not None:
            parser.error(
                "--league-id is only supported for api_football."
            )

        if not args.competition or not args.competition.strip():
            parser.error(
                "--competition is required for football_data."
            )

        competition = args.competition.strip().upper()

        if competition not in FOOTBALL_DATA_COMPETITION_IDS:
            parser.error(
                f"Unsupported competition: {competition}. "
                f"Supported: {', '.join(FOOTBALL_DATA_COMPETITION_IDS)}"
            )

        os.environ["COMPETITION_CODE"] = competition

    else:
        if args.competition is not None:
            parser.error(
                "--competition is only supported for football_data."
            )

    if args.league_id is not None:
        os.environ["LEAGUE_ID"] = str(args.league_id)

    if args.season is not None:
        os.environ["SEASON"] = str(args.season[0])

    required_variables = (
        ("LEAGUE_ID", "SEASON")
        if args.source == "api_football"
        else ("SEASON",)
)

    for variable in required_variables:
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

    seasons = args.season or [int(os.environ["SEASON"])]
    if args.ingest_only and not args.fetch:
        parser.error("--ingest-only requires --fetch.")

    for season in seasons:
        os.environ["SEASON"] = str(season)
        if args.load_only:
            if args.source == "football_data":
                script = "src/warehouse/load_football_data.py"
            else:
                script = "src/warehouse/load_fixtures.py"

            run_script(script)
            continue
        if args.transform_only:
            script = (
                "src/processing/transform_football_data.py"
                if args.source == "football_data"
                else "src/processing/transform_fixtures.py"
            )
            run_script(script)
            continue

        if args.ingest_only:
            if args.source == "football_data":
                script = "src/ingestion/fetch_football_data.py"
            else:
                script = "src/ingestion/fetch_api_football.py"

            run_script(script)
            continue

        run_for_season(args.fetch, source=args.source)
        

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)