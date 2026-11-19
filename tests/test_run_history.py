
"""Tests for local pipeline execution history."""

import json

import pytest

from src.processing.run_history import (
    load_run_history,
    print_run_history,
)


def save_report(
    root,
    run_id,
    started_at,
    status="SUCCESS",
    source="api_football",
):
    run_dir = root / run_id
    run_dir.mkdir()

    (run_dir / "pipeline.json").write_text(
        json.dumps({
            "run_id": run_id,
            "started_at": started_at,
            "source": source,
            "league_id": 39,
            "season": 2023,
            "status": status,
            "duration_seconds": 2.5,
        }),
        encoding="utf-8",
    )


def test_history_returns_newest_runs_first(tmp_path):
    save_report(
        tmp_path,
        "run_001",
        "2026-11-18T10:00:00+00:00",
    )
    save_report(
        tmp_path,
        "run_003",
        "2026-11-18T12:00:00+00:00",
    )
    save_report(
        tmp_path,
        "run_002",
        "2026-11-18T11:00:00+00:00",
    )

    history = load_run_history(tmp_path)

    assert [run["run_id"] for run in history] == [
        "run_003",
        "run_002",
        "run_001",
    ]


def test_history_limit(tmp_path):
    for number in range(5):
        save_report(
            tmp_path,
            f"run_{number}",
            f"2026-11-18T10:00:0{number}+00:00",
        )

    history = load_run_history(
        tmp_path,
        limit=2,
    )

    assert len(history) == 2


def test_history_filters_failed_runs(tmp_path):
    save_report(
        tmp_path,
        "successful",
        "2026-11-18T10:00:00+00:00",
    )
    save_report(
        tmp_path,
        "failed",
        "2026-11-18T11:00:00+00:00",
        status="FAILED",
    )

    history = load_run_history(
        tmp_path,
        status="FAILED",
    )

    assert len(history) == 1
    assert history[0]["run_id"] == "failed"


def test_history_skips_invalid_json(tmp_path):
    save_report(
        tmp_path,
        "valid",
        "2026-11-18T10:00:00+00:00",
    )

    bad_dir = tmp_path / "invalid"
    bad_dir.mkdir()
    (bad_dir / "pipeline.json").write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    history = load_run_history(tmp_path)

    assert len(history) == 1
    assert history[0]["run_id"] == "valid"


def test_history_empty_directory(tmp_path, capsys):
    history = load_run_history(tmp_path)

    assert history == []

    print_run_history(history)

    assert "No pipeline execution reports" in capsys.readouterr().out


def test_history_prints_rows(tmp_path, capsys):
    save_report(
        tmp_path,
        "run_001",
        "2026-11-18T10:00:00+00:00",
    )

    print_run_history(load_run_history(tmp_path))

    output = capsys.readouterr().out

    assert "RUN ID" in output
    assert "run_001" in output
    assert "api_football" in output
    assert "SUCCESS" in output


def test_history_rejects_invalid_limit(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        load_run_history(tmp_path, limit=0)


def test_history_reads_multi_season_report(tmp_path):
    run_dir = tmp_path / "multi_season_run"
    run_dir.mkdir()

    (run_dir / "pipeline.json").write_text(
        json.dumps({
            "schema_version": 3,
            "run_id": "multi_season_run",
            "started_at": "2026-11-19T10:00:00+00:00",
            "source": "api_football",
            "mode": "full",
            "status": "SUCCESS",
            "duration_seconds": 42.5,
            "seasons": [
                {"season": 2022, "status": "SUCCESS"},
                {"season": 2023, "status": "SUCCESS"},
                {"season": 2024, "status": "SUCCESS"},
            ],
        }),
        encoding="utf-8",
    )

    history = load_run_history(tmp_path)

    assert len(history) == 1
    assert history[0]["seasons"] == [2022, 2023, 2024]
    assert history[0]["mode"] == "full"
    assert history[0]["status"] == "SUCCESS"


def test_history_still_reads_old_report(tmp_path):
    run_dir = tmp_path / "old_run"
    run_dir.mkdir()

    (run_dir / "pipeline.json").write_text(
        json.dumps({
            "schema_version": 2,
            "run_id": "old_run",
            "started_at": "2026-11-18T10:00:00+00:00",
            "source": "api_football",
            "season": 2023,
            "status": "FAILED",
            "duration_seconds": 3.4,
        }),
        encoding="utf-8",
    )

    history = load_run_history(tmp_path, status="FAILED")

    assert len(history) == 1
    assert history[0]["seasons"] == [2023]


def test_history_prints_all_seasons(tmp_path, capsys):
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()

    (run_dir / "pipeline.json").write_text(
        json.dumps({
            "run_id": "test_run",
            "started_at": "2026-11-19T10:00:00+00:00",
            "source": "api_football",
            "mode": "full",
            "status": "SUCCESS",
            "seasons": [
                {"season": 2022},
                {"season": 2023},
            ],
        }),
        encoding="utf-8",
    )

    print_run_history(load_run_history(tmp_path))

    output = capsys.readouterr().out

    assert "test_run" in output
    assert "2022, 2023" in output
    assert "SUCCESS" in output
