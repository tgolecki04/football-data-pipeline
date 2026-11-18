
"""Generate pipeline execution reports."""

from datetime import datetime
from pathlib import Path

from src.processing.run_context import (
    ROOT,
    write_json_atomic,
)


# Legacy destination kept temporarily for compatibility.
REPORT_DIR = ROOT / "reports"

SCHEMA_VERSION = 2


def get_report_path(league_id: int, season: int) -> Path:
    """Return the legacy report path."""

    return (
        REPORT_DIR
        / f"pipeline_report_league_{league_id}_season_{season}.json"
    )


def generate_pipeline_report(
    status: str,
    started_at: datetime,
    finished_at: datetime,
    league_id: int,
    season: int,
    stages: dict,
    *,
    source: str | None = None,
    run_id: str | None = None,
    run_dir: Path | None = None,
    stage_durations: dict | None = None,
    error: dict | None = None,
    records_loaded: int | None = None,
) -> dict:
    """Build and save a pipeline execution report."""

    if (run_id is None) != (run_dir is None):
        raise ValueError(
            "run_id and run_dir must be provided together."
        )

    duration = (finished_at - started_at).total_seconds()

    report = {
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration, 2),
        "league_id": league_id,
        "season": season,
        "stages": stages,
    }

    if run_dir is not None:
        report.update({
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "source": source,
            "stage_durations_seconds": stage_durations or {},
            "error": error,
            "records_loaded": records_loaded,
        })

        report_path = Path(run_dir) / "pipeline.json"

    else:
        # Existing callers and CI continue to work.
        report_path = get_report_path(league_id, season)

    write_json_atomic(report_path, report)

    return report
