
"""Display recent pipeline execution reports."""

import argparse
import json
from pathlib import Path

from src.processing.run_context import RUNS_DIR


def load_run_history(
    runs_dir: Path = RUNS_DIR,
    limit: int = 10,
    status: str | None = None,
) -> list[dict]:
    """Return recent runs, supporting report schemas v2 and v3."""

    if limit < 1:
        raise ValueError("limit must be positive")

    runs_dir = Path(runs_dir)

    if not runs_dir.exists():
        return []

    reports = []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        report_path = run_dir / "pipeline.json"

        if not report_path.is_file():
            continue

        try:
            report = json.loads(
                report_path.read_text(encoding="utf-8")
            )

            if not isinstance(report, dict):
                continue

            run_status = report.get("status", "UNKNOWN")

            if status is not None and run_status != status:
                continue

            season_results = report.get("seasons")

            if isinstance(season_results, list):
                seasons = [
                    item["season"]
                    for item in season_results
                    if isinstance(item, dict)
                    and isinstance(item.get("season"), int)
                ]
            else:
                # Backwards compatibility with existing v2 reports.
                season = report.get("season")
                seasons = [season] if isinstance(season, int) else []

            reports.append({
                "run_id": report.get("run_id", run_dir.name),
                "started_at": report.get("started_at", ""),
                "source": report.get("source", "unknown"),
                "mode": report.get("mode", "full"),
                "seasons": seasons,
                "status": run_status,
                "duration_seconds": report.get(
                    "duration_seconds", 0
                ),
                "path": str(report_path),
            })

        except (OSError, ValueError, TypeError):
            # Invalid or unreadable reports should not break history.
            continue

    reports.sort(
        key=lambda item: (
            str(item["started_at"]),
            str(item["run_id"]),
        ),
        reverse=True,
    )

    return reports[:limit]


def print_run_history(reports: list[dict]) -> None:
    """Print a compact overview of recent executions."""

    if not reports:
        print("No pipeline execution reports found.")
        return

    print(
        f"{'RUN ID':<30} "
        f"{'SOURCE':<16} "
        f"{'MODE':<15} "
        f"{'SEASONS':<20} "
        f"{'STATUS':<10}"
    )

    print("-" * 100)

    for report in reports:
        seasons = ", ".join(
            str(season) for season in report["seasons"]
        ) or "-"

        print(
            f"{str(report['run_id']):<30} "
            f"{str(report['source']):<16} "
            f"{str(report['mode']):<15} "
            f"{seasons:<20} "
            f"{str(report['status']):<10}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect recent pipeline executions."
    )

    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of runs to display.",
    )

    parser.add_argument(
        "--status",
        choices=("SUCCESS", "FAILED"),
        default=None,
    )

    args = parser.parse_args()

    if args.last < 1:
        parser.error("--last must be positive")

    reports = load_run_history(
        limit=args.last,
        status=args.status,
    )

    print_run_history(reports)


if __name__ == "__main__":
    main()
