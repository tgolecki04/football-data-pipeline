
"""Generate Data Quality validation reports."""

from datetime import datetime, timezone
from pathlib import Path

from src.processing.run_context import (
    ROOT,
    write_json_atomic,
)


# Legacy destination kept temporarily for compatibility.
REPORT_DIR = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "data_quality_report.json"


def generate_data_quality_report(
    checks: list[dict],
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
    source: str | None = None,
) -> dict:
    """Generate and save a Data Quality report."""

    if (run_id is None) != (run_dir is None):
        raise ValueError(
            "run_id and run_dir must be provided together."
        )

    failed_checks = sum(
        1 for check in checks
        if check["status"] == "FAIL"
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "FAIL" if failed_checks else "PASS",
        "total_checks": len(checks),
        "failed_checks": failed_checks,
        "checks": checks,
    }

    if run_dir is not None:
        report.update({
            "schema_version": 2,
            "run_id": run_id,
            "source": source,
        })

        report_path = Path(run_dir) / "data_quality.json"
    else:
        report_path = REPORT_FILE

    write_json_atomic(report_path, report)

    return report
