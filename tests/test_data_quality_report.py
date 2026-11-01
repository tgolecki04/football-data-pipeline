
import json

from src.processing import data_quality_report


def test_generate_data_quality_report_pass(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_file = report_dir / "data_quality_report.json"

    monkeypatch.setattr(data_quality_report, "REPORT_DIR", report_dir)
    monkeypatch.setattr(data_quality_report, "REPORT_FILE", report_file)

    checks = [
        {
            "name": "duplicate_fixture_ids",
            "status": "PASS",
            "failures": 0,
        },
        {
            "name": "invalid_finished_fixtures",
            "status": "PASS",
            "failures": 0,
        },
    ]

    report = data_quality_report.generate_data_quality_report(checks)

    assert report["overall_status"] == "PASS"
    assert report["total_checks"] == 2
    assert report["failed_checks"] == 0
    assert report_file.exists()

    saved_report = json.loads(report_file.read_text(encoding="utf-8"))

    assert saved_report == report


def test_generate_data_quality_report_fail(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_file = report_dir / "data_quality_report.json"

    monkeypatch.setattr(data_quality_report, "REPORT_DIR", report_dir)
    monkeypatch.setattr(data_quality_report, "REPORT_FILE", report_file)

    checks = [
        {
            "name": "duplicate_fixture_ids",
            "status": "FAIL",
            "failures": 3,
        },
        {
            "name": "invalid_finished_fixtures",
            "status": "PASS",
            "failures": 0,
        },
    ]

    report = data_quality_report.generate_data_quality_report(checks)

    assert report["overall_status"] == "FAIL"
    assert report["total_checks"] == 2
    assert report["failed_checks"] == 1
    assert report["checks"][0]["failures"] == 3
    assert report_file.exists()


def test_generate_data_quality_report_with_no_checks(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_file = report_dir / "data_quality_report.json"

    monkeypatch.setattr(data_quality_report, "REPORT_DIR", report_dir)
    monkeypatch.setattr(data_quality_report, "REPORT_FILE", report_file)

    report = data_quality_report.generate_data_quality_report([])

    assert report["overall_status"] == "PASS"
    assert report["total_checks"] == 0
    assert report["failed_checks"] == 0
