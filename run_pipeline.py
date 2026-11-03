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

def run_data_quality_checks():
    logger.info("Running data quality checks...")
    start_time = time.perf_counter()

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
        
    
    started_at = datetime.now(timezone.utc)
    pipeline_start_time = time.perf_counter()

    stages = {
        "bucket": "NOT_RUN",
        "ingestion": "SKIPPED",
        "transformation": "NOT_RUN",
        "loading": "NOT_RUN",
        "gold": "NOT_RUN",
        "data_quality": "NOT_RUN",
    }

    status = "SUCCESS"

    logger.info("Starting football data pipeline")
    logger.info(
        "Configuration: league=%s, season=%s",
        os.environ["LEAGUE_ID"],
        os.environ["SEASON"],
    )

    try:
        run_pipeline_stage(
            "bucket",
            lambda: run_script("src/storage/ensure_bucket.py"),
            stages,
        )

        if args.fetch:
            run_pipeline_stage(
                "ingestion",
                lambda: run_script(
                    "src/ingestion/fetch_api_football.py"
                ),
                stages,
            )

        run_pipeline_stage(
            "transformation",
            lambda: run_script(
                "src/processing/transform_fixtures.py"
            ),
            stages,
        )

        run_pipeline_stage(
            "loading",
            lambda: run_script(
                "src/warehouse/load_fixtures.py"
            ),
            stages,
        )

        run_pipeline_stage(
            "gold",
            create_gold_view,
            stages,
        )

        run_pipeline_stage(
            "data_quality",
            run_data_quality_checks,
            stages,
        )

    except Exception:
        status = "FAILED"
        raise

    finally:
        finished_at = datetime.now(timezone.utc)
        total_duration = time.perf_counter() - pipeline_start_time

        try:
            report = generate_pipeline_report(
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                league_id=int(os.environ["LEAGUE_ID"]),
                season=int(os.environ["SEASON"]),
                stages=stages,
            )

            logger.info(
                "Pipeline report saved | Status: %s | Duration: %.2fs",
                report["status"],
                total_duration,
            )

        except Exception:
            logger.exception("Failed to generate pipeline report")

        logger.info(
            "Pipeline %s | Total duration: %.2fs",
            status,
            total_duration,
        )



if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
