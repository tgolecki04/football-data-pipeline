import argparse
import pytest
import psycopg
import run_pipeline
from run_pipeline import positive_int
import subprocess
from run_pipeline import run_script
from pathlib import Path


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

    with caplog.at_level("ERROR"):
        with pytest.raises(subprocess.CalledProcessError):
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
