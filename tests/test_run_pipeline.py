import argparse
import subprocess
from pathlib import Path

import psycopg
import pytest

import run_pipeline
from run_pipeline import positive_int, run_script


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("39", 39),
        ("2023", 2023),
    ],
)
def test_positive_int_accepts_valid_values(value, expected):
    assert positive_int(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
        "1.5",
        "",
    ],
)
def test_positive_int_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)




def test_run_script_executes_subprocess(monkeypatch, caplog):
    calls = []

    def mock_run(command, cwd, check):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "check": check,
            }
        )

    monkeypatch.setattr(subprocess, "run", mock_run)

    with caplog.at_level("INFO"):
        run_script("src/processing/transform_fixtures.py")

    assert len(calls) == 1
    assert Path(calls[0]["command"][-1]) == (
    Path(run_pipeline.ROOT)
    / "src"
    / "processing"
    / "transform_fixtures.py"
)
    assert calls[0]["check"] is True
    assert "Script completed" in caplog.text


def test_run_script_logs_failure_and_reraises(
    monkeypatch, caplog
):
    def mock_run(command, cwd, check):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
        )

    monkeypatch.setattr(subprocess, "run", mock_run)

    with caplog.at_level("ERROR"), pytest.raises(subprocess.CalledProcessError):
        run_script("src/processing/transform_fixtures.py")

    assert "Script failed" in caplog.text


def test_main_stops_when_a_script_fails(monkeypatch):
    def mock_run_script(script_path):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=[script_path],
        )

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        mock_run_script,
    )

    monkeypatch.setattr(
        run_pipeline,
        "create_gold_view",
        lambda: pytest.fail(
            "Gold view should not be created after a failure"
        ),
    )

    monkeypatch.setattr(
        "sys.argv",
        ["run_pipeline.py", "--league-id", "39", "--season", "2023"],
    )

    with pytest.raises(subprocess.CalledProcessError):
        run_pipeline.main()


def test_main_ensures_bucket_before_others_steps(monkeypatch):
    calls = []

    monkeypatch.setattr(run_pipeline, "run_script", calls.append)
    monkeypatch.setattr(run_pipeline, "create_gold_view", lambda: None)
    monkeypatch.setattr(run_pipeline, "run_data_quality_checks", lambda: None)

    monkeypatch.setattr(
        "sys.argv",
        ["run_pipeline.py", "--fetch", "--league-id", "39", "--season", "2023"],
    )

    run_pipeline.main()

    assert calls[0] == "src/storage/ensure_bucket.py"


def test_create_gold_view_propagates_database_error(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    def mock_connect(**kwargs):
        raise psycopg.OperationalError(
            "Database connection failed"
        )

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        mock_connect,
    )

    with pytest.raises(
        psycopg.OperationalError,
        match="Database connection failed",
    ):
        run_pipeline.create_gold_view()


def test_run_data_quality_checks_passes(monkeypatch, tmp_path):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    sql_file = sql_dir / "data_quality_checks.sql"
    sql_file.write_text(
        "SELECT 'duplicate_fixture_ids' AS check_name, 0 AS failures;",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        run_pipeline,
        "ROOT",
        tmp_path,
    )
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    class FakeCursor:
        def execute(self, statement):
            pass

        def fetchone(self):
            return ("duplicate_fixture_ids", 0)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        lambda **kwargs: FakeConnection(),
    )

    run_pipeline.run_data_quality_checks()


def test_run_data_quality_checks_fails_on_invalid_data(
    monkeypatch,
    tmp_path,
):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    sql_file = sql_dir / "data_quality_checks.sql"
    sql_file.write_text(
        "SELECT 'duplicate_fixture_ids' AS check_name, 0 AS failures;",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_pipeline,
        "ROOT",
        tmp_path,
    )
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    class FakeCursor:
        def execute(self, statement):
            pass

        def fetchone(self):
            return ("duplicate_fixture_ids", 1)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        lambda **kwargs: FakeConnection(),
    )

    with pytest.raises(ValueError, match="duplicate_fixture_ids"):
        run_pipeline.run_data_quality_checks()
