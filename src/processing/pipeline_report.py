
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "pipeline_report.json"


def generate_pipeline_report(
    status: str,
    started_at: datetime,
    finished_at: datetime,
    league_id: int,
    season: int,
    stages: dict,
) -> dict:
    """Generate and save a pipeline execution report."""

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

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    REPORT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    return report
