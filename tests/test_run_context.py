
"""Tests for run identifiers and execution artifacts."""

import json

import pytest

from src.processing.run_context import (
    create_run_directory,
    create_run_id,
    write_json_atomic,
)
from src.processing.pipeline_report import generate_pipeline_report
from src.processing.data_quality_report import (
    generate_data_quality_report,
)

from datetime import datetime, timezone


def test_run_ids_are_unique():
    first = create_run_id()
    second = create_run_id()

    assert first != second
    assert first.endswith(tuple("0123456789abcdef"))


def test_create_run_directory(tmp_path):
    run_id, run_dir = create_run_directory(base_dir=tmp_path)

    assert run_dir.is_dir()
    assert run_dir.name == run_id
    assert run_dir.parent == tmp_path


def test_existing_run_directory_cannot_be_reused(tmp_path):
    create_run_directory(
        run_id="test_run_001",
        base_dir=tmp_path,
    )

    with pytest.raises(FileExistsError):
        create_run_directory(
            run_id="test_run_001",
            base_dir=tmp_path,
        )


@pytest.mark.parametrize(
    "run_id",
    ["", ".", "..", "../other", "foo/bar", r"foo\bar"],
)
def test_invalid_run_ids_are_rejected(tmp_path, run_id):
    with pytest.raises(ValueError, match="Invalid run_id"):
        create_run_directory(
            run_id=run_id,
            base_dir=tmp_path,
        )


def test_write_json_atomic(tmp_path):
    destination = tmp_path / "pipeline.json"

    write_json_atomic(destination, {"status": "SUCCESS"})

    assert json.loads(destination.read_text(
        encoding="utf-8"
    )) == {"status": "SUCCESS"}

    assert list(tmp_path.glob("*.tmp")) == []


def test_json_serialization_failure_preserves_previous_file(tmp_path):
    destination = tmp_path / "report.json"
    write_json_atomic(destination, {"status": "SUCCESS"})

    with pytest.raises(TypeError):
        write_json_atomic(
            destination,
            {"invalid": object()},
        )

    assert json.loads(
        destination.read_text(encoding="utf-8")
    ) == {"status": "SUCCESS"}


def test_two_runs_of_same_season_have_separate_reports(tmp_path):
    started = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 11, 18, 10, 1, tzinfo=timezone.utc)

    paths = []

    for _ in range(2):
        run_id, run_dir = create_run_directory(
            base_dir=tmp_path
        )

        report = generate_pipeline_report(
            status="SUCCESS",
            started_at=started,
            finished_at=finished,
            league_id=39,
            season=2023,
            stages={"loading": "SUCCESS"},
            source="api_football",
            run_id=run_id,
            run_dir=run_dir,
            stage_durations={"loading": 0.5},
            records_loaded=2,
        )

        path = run_dir / "pipeline.json"

        assert path.exists()
        assert report["schema_version"] == 2
        assert report["source"] == "api_football"
        assert report["records_loaded"] == 2
        assert report["run_id"] == run_id
        paths.append(path)

    assert paths[0] != paths[1]
    assert paths[0].exists()
    assert paths[1].exists()


def test_pipeline_and_quality_reports_share_run_id(tmp_path):
    run_id, run_dir = create_run_directory(
        base_dir=tmp_path
    )

    started = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)

    pipeline = generate_pipeline_report(
        status="SUCCESS",
        started_at=started,
        finished_at=started,
        league_id=2021,
        season=2023,
        stages={"data_quality": "SUCCESS"},
        source="football_data",
        run_id=run_id,
        run_dir=run_dir,
    )

    quality = generate_data_quality_report(
        [
            {
                "name": "duplicate_fixture_ids",
                "status": "PASS",
                "failures": 0,
            }
        ],
        source="football_data",
        run_id=run_id,
        run_dir=run_dir,
    )

    assert pipeline["run_id"] == quality["run_id"]
    assert quality["overall_status"] == "PASS"
    assert (run_dir / "pipeline.json").exists()
    assert (run_dir / "data_quality.json").exists()


def test_failed_pipeline_report_is_preserved(tmp_path):
    run_id, run_dir = create_run_directory(
        base_dir=tmp_path
    )

    started = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)

    report = generate_pipeline_report(
        status="FAILED",
        started_at=started,
        finished_at=started,
        league_id=39,
        season=2023,
        stages={"loading": "FAILED"},
        source="api_football",
        run_id=run_id,
        run_dir=run_dir,
        error={
            "stage": "loading",
            "type": "ValueError",
        },
    )

    assert report["status"] == "FAILED"
    assert report["error"]["stage"] == "loading"

    saved = json.loads(
        (run_dir / "pipeline.json").read_text(encoding="utf-8")
    )

    assert saved["status"] == "FAILED"


def test_run_dir_and_id_must_be_provided_together(tmp_path):
    started = datetime(2026, 11, 18, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="together"):
        generate_pipeline_report(
            status="SUCCESS",
            started_at=started,
            finished_at=started,
            league_id=39,
            season=2023,
            stages={},
            run_dir=tmp_path,
        )

    with pytest.raises(ValueError, match="together"):
        generate_data_quality_report(
            [],
            run_id="test_run",
        )
