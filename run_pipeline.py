import argparse
import logging
import os
import subprocess
import sys
import time
import json
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


import psycopg
from dotenv import load_dotenv

from src.processing.data_quality_report import generate_data_quality_report
from src.processing.pipeline_report import generate_pipeline_report
from src.processing.run_context import create_run_directory
from src.processing.execution_session import ExecutionSession

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




def run_script(script_path, *script_args):
    """Run a Python module and stream its output through the logger."""

    module_name = (
        script_path
        .replace("\\", "/")
        .removesuffix(".py")
        .replace("/", ".")
    )

    command = [
        sys.executable,
        "-u",
        "-m",
        module_name,
        *[str(arg) for arg in script_args],
    ]

    logger.info(
        "Starting child process | module=%s | args=%s",
        module_name,
        list(script_args),
    )

    started = time.perf_counter()

    try:
        with subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process:

            assert process.stdout is not None

            for line in process.stdout:
                message = line.rstrip("\r\n")

                if message:
                    logger.info(
                        "child[%s] | %s",
                        module_name,
                        message,
                    )

            return_code = process.wait()

        duration = time.perf_counter() - started

        if return_code != 0:
            logger.error(
                "Child process failed | module=%s | "
                "exit_code=%s | duration=%.2fs",
                module_name,
                return_code,
                duration,
            )

            raise subprocess.CalledProcessError(
                return_code,
                command,
            )

        logger.info(
            "Child process completed | module=%s | "
            "duration=%.2fs",
            module_name,
            duration,
        )

    except subprocess.CalledProcessError:
        raise

    except Exception:
        logger.exception(
            "Unable to execute child process | module=%s",
            module_name,
        )
        raise




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
            host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
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


def run_data_quality_checks(
    *,
    run_id=None,
    run_dir=None,
    source=None,
    on_report=None,
):
    logger.info("Running data quality checks...")
    start_time = time.perf_counter()

    try:
        sql_path = ROOT / "sql" / "data_quality_checks.sql"
        sql = sql_path.read_text(encoding="utf-8")

        checks = []

        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
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

        report = generate_data_quality_report(
            checks,
            run_id=run_id,
            run_dir=run_dir,
            source=source,
        )

        # Preserve results even when a Data Quality check fails.
        if on_report is not None:
            on_report(report)


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


def create_run_log_handler(run_dir):
    """Write orchestrator logs to the current run directory."""

    handler = logging.FileHandler(
        run_dir / "pipeline.log",
        encoding="utf-8",
    )

    handler.setLevel(logging.INFO)

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        )
    )

    return handler




def run_for_season(
    fetch: bool,
    source: str = "api_football",
    session: ExecutionSession | None = None,
) -> None:
    """Run one season, optionally as part of a shared execution."""

    if source not in ("api_football", "football_data"):
        raise ValueError(f"Unsupported provider: {source}")

    if source == "football_data":
        ingestion_script = "src/ingestion/fetch_football_data.py"
        transformation_script = (
            "src/processing/transform_football_data.py"
        )
        league_id = FOOTBALL_DATA_COMPETITION_IDS[
            os.environ["COMPETITION_CODE"]
        ]
    else:
        ingestion_script = "src/ingestion/fetch_api_football.py"
        transformation_script = (
            "src/processing/transform_api_football.py"
        )
        league_id = int(os.environ["LEAGUE_ID"])

    loading_script = "src/warehouse/load_to_postgres.py"
    season = int(os.environ["SEASON"])

    # Direct calls create their own artifacts.
    # CLI calls reuse the one session created in main().
    standalone = session is None

    if standalone:
        run_id, run_dir = create_run_directory()
    else:
        run_id, run_dir = session.run_id, session.run_dir

    started_at = datetime.now(timezone.utc)
    pipeline_start = time.perf_counter()

    stages = {
        "bucket": "NOT_RUN",
        "ingestion": "SKIPPED",
        "transformation": "NOT_RUN",
        "loading": "NOT_RUN",
        "gold": "NOT_RUN",
        "data_quality": "NOT_RUN",
    }

    stage_durations = {}
    status = "SUCCESS"
    error = None

    root_logger = logging.getLogger()
    run_handler = None

    if standalone:
        run_handler = create_run_log_handler(run_dir)
        root_logger.addHandler(run_handler)

    def timed_stage(name, action):
        """Run a stage and record its duration, including failures."""

        stage_start = time.perf_counter()

        try:
            return run_pipeline_stage(
                name,
                action,
                stages,
            )
        finally:
            stage_durations[name] = round(
                time.perf_counter() - stage_start,
                3,
            )

    def collect_quality_report(report):
        """Preserve Data Quality results before an error is raised."""

        if session is None:
            return

        session.quality_results.append({
            "league_id": league_id,
            "season": season,
            "overall_status": report["overall_status"],
            "total_checks": report["total_checks"],
            "failed_checks": report["failed_checks"],
            "checks": report["checks"],
        })

    try:
        logger.info(
            "Pipeline started | run_id=%s | "
            "source=%s | league=%s | season=%s",
            run_id,
            source,
            league_id,
            season,
        )

        timed_stage(
            "bucket",
            lambda: run_script(
                "src/storage/ensure_bucket.py"
            ),
        )

        if fetch:
            timed_stage(
                "ingestion",
                lambda: run_script(ingestion_script),
            )

        timed_stage(
            "transformation",
            lambda: run_script(transformation_script),
        )

        timed_stage(
            "loading",
            lambda: run_script(
                loading_script,
                "--source",
                source,
            ),
        )

        timed_stage(
            "gold",
            create_gold_view,
        )

        timed_stage(
            "data_quality",
            lambda: run_data_quality_checks(
                run_id=run_id,
                run_dir=run_dir,
                source=source,
                on_report=collect_quality_report,
            ),
        )

    except Exception as exc:
        status = "FAILED"

        failed_stage = next(
            (
                name
                for name, stage_status in stages.items()
                if stage_status == "FAILED"
            ),
            None,
        )

        # Avoid putting exception messages or credentials in JSON.
        error = {
            "type": type(exc).__name__,
            "stage": failed_stage,
        }

        logger.exception(
            "Pipeline failed | run_id=%s | "
            "season=%s | stage=%s",
            run_id,
            season,
            failed_stage,
        )

        raise

    finally:
        finished_at = datetime.now(timezone.utc)
        total_duration = time.perf_counter() - pipeline_start

        # Record this season in the shared execution session.
        if session is not None:
            session.seasons.append({
                "league_id": league_id,
                "season": season,
                "status": status,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": round(total_duration, 3),
                "stages": dict(stages),
                "stage_durations_seconds": dict(stage_durations),
                "error": error,
            })

        # Preserve existing standalone behavior for direct callers.
        if standalone:
            try:
                report = generate_pipeline_report(
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    league_id=league_id,
                    season=season,
                    stages=stages,
                    source=source,
                    run_id=run_id,
                    run_dir=run_dir,
                    stage_durations=stage_durations,
                    error=error,
                )

                logger.info(
                    "Pipeline finished | run_id=%s | "
                    "status=%s | duration=%.2fs",
                    run_id,
                    report["status"],
                    total_duration,
                )

                logger.info(
                    "Execution artifacts: %s",
                    run_dir,
                )

            except Exception:
                logger.exception(
                    "Failed to generate pipeline report | "
                    "run_id=%s",
                    run_id,
                )

                # Do not hide reporting errors after a successful ETL.
                # Preserve the original exception if ETL already failed.
                if status == "SUCCESS":
                    raise

            finally:
                root_logger.removeHandler(run_handler)
                run_handler.close()



def run_partial_pipeline(
    mode: str,
    source: str,
    session: ExecutionSession | None = None,
) -> None:
    """Run one requested stage with its own log and JSON report."""

    scripts = {
        "ingestion": {
            "api_football": "src/ingestion/fetch_api_football.py",
            "football_data": "src/ingestion/fetch_football_data.py",
        },
        "transformation": {
            "api_football": "src/processing/transform_api_football.py",
            "football_data": "src/processing/transform_football_data.py",
        },
        "loading": {
            "api_football": "src/warehouse/load_to_postgres.py",
            "football_data": "src/warehouse/load_to_postgres.py",
        },
    }

    if mode not in scripts:
        raise ValueError(f"Unsupported partial mode: {mode}")

    if source not in scripts[mode]:
        raise ValueError(f"Unsupported source: {source}")

    league_id = (
        FOOTBALL_DATA_COMPETITION_IDS[os.environ["COMPETITION_CODE"]]
        if source == "football_data"
        else int(os.environ["LEAGUE_ID"])
    )
    season = int(os.environ["SEASON"])

    standalone = session is None

    if standalone:
        run_id, run_dir = create_run_directory()
    else:
        run_id, run_dir = session.run_id, session.run_dir

    started_at = datetime.now(timezone.utc)
    start = time.perf_counter()

    stages = {
        "bucket": "NOT_RUN",
        "ingestion": "NOT_RUN",
        "transformation": "NOT_RUN",
        "loading": "NOT_RUN",
        "gold": "NOT_RUN",
        "data_quality": "NOT_RUN",
    }
    stage_durations = {}
    status = "SUCCESS"
    error = None

    handler = None
    root_logger = logging.getLogger()

    if standalone:
        handler = create_run_log_handler(run_dir)
        root_logger.addHandler(handler)

    try:
        logger.info(
            "Partial pipeline started | run_id=%s | "
            "mode=%s | source=%s | league=%s | season=%s",
            run_id, mode, source, league_id, season,
        )

        stage_start = time.perf_counter()

        try:
            script = scripts[mode][source]

            def execute():
                if mode == "loading":
                    return run_script(script, "--source", source)
                return run_script(script)

            run_pipeline_stage(mode, execute, stages)

        finally:
            stage_durations[mode] = round(
                time.perf_counter() - stage_start, 3
            )

    except Exception as exc:
        status = "FAILED"
        error = {
            "stage": mode,
            "type": type(exc).__name__,
        }

        logger.exception(
            "Partial pipeline failed | run_id=%s",
            run_id,
        )
        raise

    finally:
        finished_at = datetime.now(timezone.utc)

        if session is not None:
            session.seasons.append({
                "league_id": league_id,
                "season": season,
                "status": status,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": round(
                    time.perf_counter() - start, 3
                ),
                "stages": dict(stages),
                "stage_durations_seconds": dict(stage_durations),
                "error": error,
            })

        if standalone:
            try:
                report = generate_pipeline_report(
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    league_id=league_id,
                    season=season,
                    stages=stages,
                    source=source,
                    run_id=run_id,
                    run_dir=run_dir,
                    stage_durations=stage_durations,
                    error=error,
                )

                logger.info(
                    "Partial pipeline finished | "
                    "run_id=%s | status=%s",
                    run_id,
                    report["status"],
                )

            except Exception:
                logger.exception(
                    "Failed to save partial pipeline report"
                )
                if status == "SUCCESS":
                    raise

            finally:
                root_logger.removeHandler(handler)
                handler.close()



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
        mode = (
            "loading" if args.load_only
            else "transformation" if args.transform_only
            else "ingestion" if args.ingest_only
            else "full"
        )

        session = ExecutionSession.create(
            source=args.source,
            mode=mode,
        )

        root_logger = logging.getLogger()
        run_handler = create_run_log_handler(session.run_dir)
        root_logger.addHandler(run_handler)

        logger.info(
            "Execution started | run_id=%s | "
            "source=%s | mode=%s | seasons=%s",
            session.run_id,
            session.source,
            session.mode,
            seasons,
        )

        try:
            for season in seasons:
                os.environ["SEASON"] = str(season)

                if args.load_only:
                    run_partial_pipeline(
                        mode="loading",
                        source=args.source,
                        session=session,
                    )

                elif args.transform_only:
                    run_partial_pipeline(
                        mode="transformation",
                        source=args.source,
                        session=session,
                    )

                elif args.ingest_only:
                    run_partial_pipeline(
                        mode="ingestion",
                        source=args.source,
                        session=session,
                    )

                else:
                    run_for_season(
                        args.fetch,
                        source=args.source,
                        session=session,
                    )

        finally:
            try:
                session.save_reports()

                logger.info(
                    "Execution artifacts saved | run_id=%s | "
                    "directory=%s",
                    session.run_id,
                    session.run_dir,
                )

            finally:
                root_logger.removeHandler(run_handler)
                run_handler.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)