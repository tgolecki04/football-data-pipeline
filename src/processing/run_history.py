
"""Inspect local pipeline execution history."""

import argparse
import json
from pathlib import Path

from src.processing.run_context import RUNS_DIR


def load_run_history(
    runs_dir: Path = RUNS_DIR,
    limit: int = 10,
    status: str | None = None,
) -> list[dict]:
    """Read latest execution reports without modifying them."""

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
        except (OSError, json.JSONDecodeError):
            # A broken report must not prevent reading other runs.
            continue

        if not isinstance(report, dict):
            continue

        if status is not None and report.get("status") != status:
            continue

        reports.append({
            "run_id": report.get("run_id", run_dir.name),
            "started_at": report.get("started_at", ""),
            "source": report.get("source", "unknown"),
            "league_id": report.get("league_id", "-"),
            "season": report.get("season", "-"),
            "status": report.get("status", "UNKNOWN"),
            "duration_seconds": report.get(
                "duration_seconds", 0
            ),
            "path": str(report_path),
        })

    reports.sort(
        key=lambda report: (
            report["started_at"],
            report["run_id"],
        ),
        reverse=True,
    )

    return reports[:limit]


def print_run_history(reports: list[dict]) -> None:
    """Display a readable terminal table."""

    if not reports:
        print("No pipeline execution reports found.")
        return

    print(
        f"{'RUN ID':34} "
        f"{'SOURCE':15} "
        f"{'LEAGUE':>7} "
        f"{'SEASON':>6} "
        f"{'STATUS':10} "
        f"{'TIME':>10}"
    )

    print("-" * 91)

    for report in reports:
        run_id = str(report["run_id"])[:34]
        source = str(report["source"])[:15]
        league = str(report["league_id"])
        season = str(report["season"])
        status = str(report["status"])[:10]
        duration = report["duration_seconds"]

        try:
            duration_text = f"{float(duration):.2f}s"
        except (TypeError, ValueError):
            duration_text = "-"

        print(
            f"{run_id:34} "
            f"{source:15} "
            f"{league:>7} "
            f"{season:>6} "
            f"{status:10} "
            f"{duration_text:>10}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show recent pipeline executions."
    )

    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of runs to show (default: 10).",
    )

    parser.add_argument(
        "--status",
        choices=["SUCCESS", "FAILED"],
        help="Show only runs with the selected status.",
    )

    args = parser.parse_args()

    if args.last < 1:
        parser.error("--last must be positive.")

    reports = load_run_history(
        limit=args.last,
        status=args.status,
    )

    print_run_history(reports)


if __name__ == "__main__":
    main()
