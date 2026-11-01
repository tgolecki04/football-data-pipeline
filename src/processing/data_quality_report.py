
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "data_quality_report.json"


def generate_data_quality_report(checks: list[dict]) -> dict:
    """Generate and save a data quality report."""

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

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    REPORT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    return report
