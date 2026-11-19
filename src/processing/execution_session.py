
"""Shared execution state for one pipeline CLI invocation."""

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from src.processing.run_context import (
    create_run_directory,
    write_json_atomic,
)


@dataclass
class ExecutionSession:
    run_id: str
    run_dir: Path
    source: str
    mode: str
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    seasons: list[dict] = field(default_factory=list)
    quality_results: list[dict] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        source: str,
        mode: str,
        base_dir: Path | None = None,
    ) -> "ExecutionSession":
        run_id, run_dir = create_run_directory(
            base_dir=base_dir
        )
        return cls(
            run_id=run_id,
            run_dir=run_dir,
            source=source,
            mode=mode,
        )

    def save_reports(self) -> None:
        finished_at = datetime.now(timezone.utc)

        status = (
            "FAILED"
            if any(
                season["status"] == "FAILED"
                for season in self.seasons
            )
            else "SUCCESS"
        )

        pipeline_report = {
            "schema_version": 3,
            "run_id": self.run_id,
            "execution_type": "local",
            "source": self.source,
            "mode": self.mode,
            "status": status,
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(),
                3,
            ),
            "seasons": self.seasons,
        }

        write_json_atomic(
            self.run_dir / "pipeline.json",
            pipeline_report,
        )

        if self.quality_results:
            total_checks = sum(
                result["total_checks"]
                for result in self.quality_results
            )
            failed_checks = sum(
                result["failed_checks"]
                for result in self.quality_results
            )

            write_json_atomic(
                self.run_dir / "data_quality.json",
                {
                    "schema_version": 3,
                    "run_id": self.run_id,
                    "overall_status": (
                        "FAIL" if failed_checks else "PASS"
                    ),
                    "total_checks": total_checks,
                    "failed_checks": failed_checks,
                    "seasons": self.quality_results,
                },
            )
